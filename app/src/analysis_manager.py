"""Backward-compatible re-exports from application services."""
from __future__ import annotations

from .application.services.analysis_service import (
    AnalysisService,
    get_analysis_service,
    reset_analysis_service,
)
from .application.services.space_service import SpaceService
from .models.requests import StartAnalysisRequest

_space_service = SpaceService()
_analysis_service = get_analysis_service()

# Legacy module-level globals for any direct imports
analysis_states = _analysis_service._store.analysis_states
spaces = _analysis_service._store.spaces
space_history = _analysis_service._store.space_history


def create_space() -> str:
    return _space_service.create_space()


def get_space(space_id: str) -> list[str]:
    return _space_service.get_space(space_id)


def delete_space(space_id: str) -> bool:
    return _space_service.delete_space(space_id)


def start_analysis(request: StartAnalysisRequest) -> str:
    return _analysis_service.start_analysis(request)


def stop_analysis(analysis_id: str) -> bool:
    return _analysis_service.stop_analysis(analysis_id)


def get_analysis_state(analysis_id: str):
    return _analysis_service.get_analysis_state(analysis_id)


__all__ = [
    "AnalysisService",
    "analysis_states",
    "spaces",
    "space_history",
    "create_space",
    "get_space",
    "delete_space",
    "start_analysis",
    "stop_analysis",
    "get_analysis_state",
    "get_analysis_service",
    "reset_analysis_service",
]
