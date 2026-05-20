"""Shared test fixtures."""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch):
    """Give each test an isolated datasource root and reset singletons."""
    root = tmp_path / "datasources"
    root.mkdir()
    monkeypatch.setenv("DATASOURCE_ROOT", str(root))
    monkeypatch.setenv("CODE_RUNNER_URL", "http://sandbox:8001/")
    monkeypatch.setenv("CONTEXT_ENGINE_URL", "http://context-engine:8002/")

    from src.core.config import reset_settings_cache
    from src.datasource_registry import reset_registry
    from src.application.services.analysis_state_store import reset_analysis_state_store
    from src.application.services.analysis_service import reset_analysis_service
    from src.application.services.prompt_service import reset_prompt_service
    from src.infrastructure.external.llm_client import reset_llm_client

    reset_settings_cache()
    reset_registry()
    reset_analysis_state_store()
    reset_analysis_service()
    reset_prompt_service()
    reset_llm_client()

    yield root

    reset_settings_cache()
    reset_registry()
    reset_analysis_state_store()
    reset_analysis_service()
    reset_prompt_service()
    reset_llm_client()
