"""Prompt assembly utilities.

The legacy version pulled a PostgreSQL schema markdown blob on every
request. After the multi-datasource refactor we instead aggregate schema
information from the :class:`DatasourceRegistry` so the LLM is aware of
*every* registered source (CSV, Excel, SQLite, Postgres, ...).
"""
from __future__ import annotations

import os
from typing import Dict, Iterable, List

from ..datasource_registry import get_registry

# Load prompt files (unchanged paths/contents)
prompts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")
with open(os.path.join(prompts_dir, "prompt-v3.txt"), "r", encoding="utf-8") as f:
    PromptText = f.read()
with open(os.path.join(prompts_dir, "prompt-v3+.txt"), "r", encoding="utf-8") as f:
    PromptText_with_Example = f.read()


# Cached schema blocks keyed by DuckDB view name.
databaseinfo: Dict[str, str] = {}


def get_db_embedded_prompt(tables: Iterable[str] | None = None) -> List[str]:
    """Return ``[PromptText_with_Example, PromptText]`` with schema injected.

    ``tables`` is an optional iterable of view names to filter on.
    """
    tables = list(tables or [])
    if not tables:
        # Every registered view
        tables = list(databaseinfo.keys())

    seen: set[str] = set()
    info_parts: List[str] = []
    for table in tables:
        block = databaseinfo.get(table)
        if not block or block in seen:
            continue
        seen.add(block)
        info_parts.append(block)

    dbinfo = "\n\n".join(info_parts)
    return [
        PromptText_with_Example.replace("@databaseinfo", dbinfo),
        PromptText.replace("@databaseinfo", dbinfo),
    ]


def set_db_schema() -> None:
    """Refresh the cached schema map from the datasource registry."""
    global databaseinfo
    schema_by_view: Dict[str, str] = {}
    for record in get_registry().list_datasources():
        if not record.schema_markdown:
            continue
        for view_name in record.view_names:
            schema_by_view[view_name] = record.schema_markdown
    databaseinfo = schema_by_view


def is_database_registered() -> bool:
    """True when at least one datasource is registered."""
    if databaseinfo:
        return True
    # Fall back to a fresh registry check in case ``set_db_schema`` wasn't
    # called recently.
    return any(get_registry().list_datasources())
