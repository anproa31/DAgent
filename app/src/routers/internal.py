"""Internal endpoints consumed by sister services (agent-service, sandbox).

Returns the multi-datasource schema map keyed by DuckDB view name. Each
value is the rendered Markdown schema block for the *whole* datasource
that view belongs to, so the agent-service can reason about adjacent
tables when relevant.

``GET /internal/schema`` also exposes semantic context from the context-engine:
a top-level ``context`` blob (all matching datasources), and
``context_by_view`` aligned with the ``schema`` keys for per-view lookups.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from ..datasource_registry import get_registry

router = APIRouter(prefix="/internal")


@router.get("/schema")
async def get_schema(tables: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Return schema markdown and semantic context keyed by DuckDB view name.

    **Response fields**

    - ``schema``: markdown schema per view (full datasource block repeated per view).
    - ``context_by_view``: context-engine markdown for the datasource that owns each
      view (same keys as ``schema``; empty string when no context was built).
    - ``context``: all distinct datasource context summaries that match the filter,
      concatenated (same selection rules as ``combined`` for which datasources appear;
      may include summaries for datasources that have context but no ``schema`` block).
    - ``combined``: context + schema + cross-datasource join hints (see registry).

    ``tables`` is an optional comma-separated list of view names to limit which
    views (and their datasources) are included.
    """
    registry = get_registry()
    requested_views: Optional[List[str]] = None
    if tables:
        requested_views = [t.strip() for t in tables.split(",") if t.strip()]

    schema_by_view: Dict[str, str] = {}
    context_by_view: Dict[str, str] = {}
    for record in registry.list_datasources():
        if not record.schema_markdown:
            continue
        for view_name in record.view_names:
            if requested_views is not None and view_name not in requested_views:
                continue
            schema_by_view[view_name] = record.schema_markdown
            context_by_view[view_name] = record.context_summary or ""

    combined = registry.aggregate_schema_markdown(view_names=requested_views)

    context_parts: List[str] = []
    for record in registry.list_datasources():
        if not record.context_summary:
            continue
        if requested_views is None or any(v in requested_views for v in record.view_names):
            context_parts.append(record.context_summary)

    return {
        "schema": schema_by_view,
        "combined": combined,
        "context": "\n\n".join(context_parts) if context_parts else "",
        "context_by_view": context_by_view,
    }


@router.get("/datasources")
async def get_datasources() -> Dict[str, Any]:
    """Structured datasource list used by agents to plan SQL vs Python paths."""
    registry = get_registry()
    payload: List[Dict[str, Any]] = []
    for record in registry.list_datasources():
        payload.append(
            {
                "id": record.id,
                "name": record.name,
                "kind": record.kind.value,
                "type": record.type,
                "view_names": record.view_names,
                "tables": [t.model_dump() for t in record.tables],
            }
        )
    return {"datasources": payload}


@router.get("/sandbox-bootstrap")
async def sandbox_bootstrap() -> Dict[str, Any]:
    """Full DDL bundle for the sandbox to recreate its DuckDB catalog.

    The sandbox calls this on startup so every registered view is
    re-applied, even when its persistent DuckDB file is fresh (or got
    cleared) and regardless of which container restarted last.
    """
    registry = get_registry()
    payload: List[Dict[str, Any]] = []
    for record, snippets in registry.rebuild_all_views_snippets():
        payload.append(
            {
                "datasource_id": record.id,
                "name": record.name,
                "kind": record.kind.value,
                "type": record.type,
                "view_names": record.view_names,
                "config": record.config,
                "sql_snippets": snippets,
            }
        )
    return {"datasources": payload}
