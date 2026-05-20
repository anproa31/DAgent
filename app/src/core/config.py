"""Centralized application configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    datasource_root: str
    code_runner_url: str
    context_engine_url: str
    host: str
    port: int
    reload: bool

    @property
    def sandbox_url(self) -> str:
        return self.code_runner_url.rstrip("/")

    @property
    def registry_path(self) -> str:
        return os.path.join(self.datasource_root, "registry.json")

    @property
    def files_dir(self) -> str:
        return os.path.join(self.datasource_root, "files")


@lru_cache
def get_settings() -> Settings:
    return Settings(
        datasource_root=os.environ.get("DATASOURCE_ROOT", "/data/datasources"),
        code_runner_url=os.environ.get("CODE_RUNNER_URL", "http://sandbox:8001/"),
        context_engine_url=os.environ.get(
            "CONTEXT_ENGINE_URL", "http://context-engine:8002/"
        ),
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
        reload=os.environ.get("RELOAD", "1") not in ("0", "false", "False"),
    )


def reset_settings_cache() -> None:
    """Clear cached settings (used in tests)."""
    get_settings.cache_clear()
