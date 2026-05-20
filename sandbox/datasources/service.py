"""Datasource register/unregister business logic."""
from __future__ import annotations

import re
from typing import Any, Dict, List

from api.schemas import RegisterDatasourceRequest, UnregisterDatasourceRequest
from datasources import registry, snippets
from infrastructure.duckdb import get_connection
from infrastructure.logging_setup import logger


def register(request: RegisterDatasourceRequest) -> Dict[str, Any]:
    for snippet in request.sql_snippets:
        snippets.apply_snippet(snippet, request)
    registry.set_record(
        request.datasource_id,
        {
            "name": request.name,
            "type": request.type,
            "view_names": list(request.view_names),
            "config": dict(request.config),
            "sql_snippets": list(request.sql_snippets),
        },
    )
    return {"ok": True, "view_names": request.view_names}


def unregister(request: UnregisterDatasourceRequest) -> Dict[str, Any]:
    record = registry.pop(request.datasource_id)
    view_names: List[str] = (
        list(request.view_names)
        if request.view_names
        else (record["view_names"] if record else [])
    )

    conn = get_connection()
    for view in view_names:
        try:
            conn.execute(f'DROP VIEW IF EXISTS "{view}"')
        except Exception as exc:
            logger.warning("Failed to drop view %s: %s", view, exc)

    if record:
        for snippet in record.get("sql_snippets", []):
            if snippet.startswith("ATTACH"):
                match = re.search(
                    r'ATTACH\s+\'[^\']+\'\s+AS\s+"?([^"\s\(]+)"?',
                    snippet,
                    re.IGNORECASE,
                )
                if match:
                    alias = match.group(1)
                    try:
                        conn.execute(f'DETACH "{alias}"')
                    except Exception as exc:
                        logger.info("Detach of %s skipped: %s", alias, exc)

    return {"ok": True, "removed": view_names}
