"""Backward-compatible prompt utilities delegating to PromptService."""
from __future__ import annotations

from typing import Dict, Iterable, List

from ..application.services.prompt_service import get_prompt_service, reset_prompt_service

_prompt_service = get_prompt_service()

# Legacy module-level cache reference
databaseinfo: Dict[str, str] = _prompt_service._schema_by_view


def get_db_embedded_prompt(tables: Iterable[str] | None = None) -> List[str]:
    return _prompt_service.get_db_embedded_prompt(tables)


def set_db_schema() -> None:
    global databaseinfo
    _prompt_service.refresh_schema_cache()
    databaseinfo = _prompt_service._schema_by_view


def is_database_registered() -> bool:
    return _prompt_service.is_database_registered()
