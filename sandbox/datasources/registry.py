"""In-memory mirror of registered datasource metadata."""
from __future__ import annotations

from typing import Any, Dict

_datasources: Dict[str, Dict[str, Any]] = {}


def get_all() -> Dict[str, Dict[str, Any]]:
    return _datasources


def get(datasource_id: str) -> Dict[str, Any] | None:
    return _datasources.get(datasource_id)


def set_record(datasource_id: str, record: Dict[str, Any]) -> None:
    _datasources[datasource_id] = record


def pop(datasource_id: str) -> Dict[str, Any] | None:
    return _datasources.pop(datasource_id, None)


def count() -> int:
    return len(_datasources)


def total_view_count() -> int:
    return sum(len(d["view_names"]) for d in _datasources.values())
