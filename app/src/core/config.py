"""Centralized application configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    datasource_root: str
    code_runner_url: str
    dce_domain_dir: str
    host: str
    port: int
    reload: bool
    web_fetch_max_bytes: int
    web_fetch_timeout: float
    web_discover_max_search: int
    web_discover_max_fetch: int
    web_allow_untrusted: bool

    @property
    def sandbox_url(self) -> str:
        return self.code_runner_url.rstrip("/")

    @property
    def registry_path(self) -> str:
        return os.path.join(self.datasource_root, "registry.json")

    @property
    def files_dir(self) -> str:
        return os.path.join(self.datasource_root, "files")

    @property
    def dce_domain_path(self) -> str:
        return self.dce_domain_dir


@lru_cache
def get_settings() -> Settings:
    return Settings(
        datasource_root=os.environ.get("DATASOURCE_ROOT", "/data/datasources"),
        code_runner_url=os.environ.get("CODE_RUNNER_URL", "http://sandbox:8001/"),
        dce_domain_dir=os.environ.get(
            "DCE_DOMAIN_DIR",
            os.path.join(
                os.environ.get("DATASOURCE_ROOT", "/data/datasources"),
                "dce_domain",
            ),
        ),
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        reload=os.environ.get("RELOAD", "1") not in ("0", "false", "False"),
        web_fetch_max_bytes=int(os.environ.get("WEB_FETCH_MAX_BYTES", str(50 * 1024 * 1024))),
        web_fetch_timeout=float(os.environ.get("WEB_FETCH_TIMEOUT", "30")),
        web_discover_max_search=int(os.environ.get("WEB_DISCOVER_MAX_SEARCH", "10")),
        web_discover_max_fetch=int(os.environ.get("WEB_DISCOVER_MAX_FETCH", "3")),
        web_allow_untrusted=os.environ.get("WEB_ALLOW_UNTRUSTED", "0") in ("1", "true", "True"),
    )


def reset_settings_cache() -> None:
    """Clear cached settings (used in tests)."""
    get_settings.cache_clear()
