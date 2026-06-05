"""Bootstrap and Ollama wiring for the databao-context-engine library."""
from __future__ import annotations

import importlib
import logging
import os
import threading
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import Optional, Tuple
from urllib.parse import urlparse

from databao_context_engine import (
    DatabaoContextDomainManager,
    InitDomainError,
    init_dce_domain,
    init_or_get_dce_domain,
)
from databao_context_engine.project.layout import is_project_dir_valid

logger = logging.getLogger(__name__)

_PATCH_LOCK = threading.Lock()
_PATCHED = False


def parse_ollama_endpoint(
    *,
    host_env: str = "DCE_OLLAMA_HOST",
    port_env: str = "DCE_OLLAMA_PORT",
    url_env: str = "DCE_OLLAMA_URL",
    default_host: str = "host.docker.internal",
    default_port: int = 11434,
) -> Tuple[str, int]:
    """Resolve Ollama host/port for DCE embedding calls."""
    url = os.environ.get(url_env, "").strip()
    if url:
        parsed = urlparse(url if "://" in url else f"http://{url}")
        host = parsed.hostname or default_host
        port = parsed.port or default_port
        return host, port

    host = os.environ.get(host_env, default_host).strip() or default_host
    try:
        port = int(os.environ.get(port_env, str(default_port)))
    except (TypeError, ValueError):
        port = default_port
    return host, port


def _rebind_factory_consumers(factory: ModuleType) -> None:
    """DCE submodules import factory helpers by value; rebind after patching."""
    consumer_modules = (
        "databao_context_engine.build_sources.build_wiring",
        "databao_context_engine.search_context.search_wiring",
        "databao_context_engine.llm.api",
    )
    bindings = (
        "create_ollama_service",
        "create_ollama_embedding_provider",
        "create_ollama_description_provider",
        "create_ollama_prompt_provider",
    )
    for module_name in consumer_modules:
        mod = importlib.import_module(module_name)
        for name in bindings:
            if hasattr(mod, name):
                setattr(mod, name, getattr(factory, name))


def patch_dce_ollama(*, host: Optional[str] = None, port: Optional[int] = None) -> Tuple[str, int]:
    """Point DCE at an external Ollama instance (Compose: host.docker.internal)."""
    global _PATCHED
    resolved_host, resolved_port = host, port
    if resolved_host is None or resolved_port is None:
        parsed_host, parsed_port = parse_ollama_endpoint()
        resolved_host = resolved_host or parsed_host
        resolved_port = resolved_port or parsed_port

    with _PATCH_LOCK:
        if _PATCHED:
            return resolved_host, resolved_port

        import databao_context_engine.llm.factory as factory
        import databao_context_engine.llm.install as install_module

        remote = resolved_host not in {"127.0.0.1", "localhost"}
        original_resolve_bin = install_module.resolve_ollama_bin
        original_create_common = factory._create_ollama_service_common
        original_create_service = factory.create_ollama_service
        original_create_embedding = factory.create_ollama_embedding_provider
        original_create_description = factory.create_ollama_description_provider
        original_create_prompt = factory.create_ollama_prompt_provider

        def create_ollama_service(*, host: str = "127.0.0.1", port: int = 11434, ensure_ready: bool = True):
            return original_create_service(
                host=resolved_host,
                port=resolved_port,
                ensure_ready=False if remote else ensure_ready,
            )

        def create_ollama_embedding_provider(service, *, model_details, pull_if_needed: bool = True):
            return original_create_embedding(
                service,
                model_details=model_details,
                pull_if_needed=False if remote else pull_if_needed,
            )

        def create_ollama_description_provider(service, *, model_id=None, pull_if_needed: bool = True):
            kwargs = {"pull_if_needed": False if remote else pull_if_needed}
            if model_id is not None:
                kwargs["model_id"] = model_id
            return original_create_description(service, **kwargs)

        def create_ollama_prompt_provider(service, *, model_id=None, pull_if_needed: bool = True):
            kwargs = {"pull_if_needed": False if remote else pull_if_needed}
            if model_id is not None:
                kwargs["model_id"] = model_id
            return original_create_prompt(service, **kwargs)

        def resolve_ollama_bin():
            # DCE always resolves a binary even for HTTP-only remote Ollama; skip bundled download.
            if remote:
                return os.environ.get("DCE_OLLAMA_BIN", "/bin/sh")
            return original_resolve_bin()

        def _create_ollama_service_common(*, host: str, port: int, ensure_ready: bool):
            # factory.py imports resolve_ollama_bin by value; patch the helper it actually calls.
            if remote:
                from databao_context_engine.llm.config import OllamaConfig
                from databao_context_engine.llm.service import OllamaService

                return OllamaService(
                    OllamaConfig(
                        host=host,
                        port=port,
                        bin_path=os.environ.get("DCE_OLLAMA_BIN", "/bin/sh"),
                    )
                )
            return original_create_common(host=host, port=port, ensure_ready=ensure_ready)

        factory.create_ollama_service = create_ollama_service
        factory.create_ollama_embedding_provider = create_ollama_embedding_provider
        factory.create_ollama_description_provider = create_ollama_description_provider
        factory.create_ollama_prompt_provider = create_ollama_prompt_provider
        factory._create_ollama_service_common = _create_ollama_service_common
        factory.resolve_ollama_bin = resolve_ollama_bin
        install_module.resolve_ollama_bin = resolve_ollama_bin
        _rebind_factory_consumers(factory)
        _PATCHED = True
        logger.info("DCE Ollama patched to %s:%s (remote=%s)", resolved_host, resolved_port, remote)

    return resolved_host, resolved_port


def resolve_embedding_model() -> Tuple[str, int]:
    """Map deployment embedding env vars to DCE project config."""
    model = os.environ.get("DCE_EMBEDDING_MODEL") or os.environ.get(
        "EMBEDDING_MODEL", "nomic-embed-text-v2-moe"
    )
    # Legacy aliases -> the model actually pulled in Ollama.
    if model in {"nomic-embed-text", "nomic-embed-text:v1.5"}:
        model = "nomic-embed-text-v2-moe"
    try:
        dims = int(os.environ.get("DCE_EMBEDDING_DIMS") or os.environ.get("EMBEDDING_DIMS", "768"))
    except (TypeError, ValueError):
        dims = 768
    return model, dims


@lru_cache
def get_domain_manager(domain_dir: str) -> DatabaoContextDomainManager:
    """Return a process-wide DatabaoContextDomainManager for ``domain_dir``.

    The directory is created on first use and initialized with our embedding
    model; subsequent calls reuse the existing domain. ``init_dce_domain``
    requires the directory to already exist, so mkdir before initializing.
    """
    patch_dce_ollama()
    path = Path(domain_dir)
    path.mkdir(parents=True, exist_ok=True)
    if is_project_dir_valid(path):
        return init_or_get_dce_domain(path)

    model_id, model_dim = resolve_embedding_model()
    try:
        return init_dce_domain(path, ollama_model_id=model_id, ollama_model_dim=model_dim)
    except InitDomainError:
        # Another process initialized the domain between the check and now.
        return init_or_get_dce_domain(path)


def reset_domain_manager_cache() -> None:
    """Clear cached domain manager (tests)."""
    get_domain_manager.cache_clear()
