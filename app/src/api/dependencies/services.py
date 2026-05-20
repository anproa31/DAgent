"""FastAPI dependency injection for application services."""
from __future__ import annotations

from functools import lru_cache

from ...application.services.analysis_service import AnalysisService, get_analysis_service
from ...application.services.prompt_service import PromptService, get_prompt_service
from ...application.services.space_service import SpaceService
from ...datasource_registry import DatasourceRegistry, get_registry
from ...infrastructure.external.llm_client import LLMClient, get_llm_client


@lru_cache
def get_space_service() -> SpaceService:
    return SpaceService()


def get_datasource_registry() -> DatasourceRegistry:
    return get_registry()


def get_prompt_service_dep() -> PromptService:
    return get_prompt_service()


def get_analysis_service_dep() -> AnalysisService:
    return get_analysis_service()


def get_llm_client_dep() -> LLMClient:
    return get_llm_client()
