"""Internal endpoints consumed by sister services (agent-service, sandbox).

Returns the multi-datasource schema map keyed by DuckDB view name. Each
value is the rendered Markdown schema block for the *whole* datasource
that view belongs to, so the agent-service can reason about adjacent
tables when relevant.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Query

from ..datasource_registry import get_registry

router = APIRouter(prefix="/internal")


@router.get("/schema")
async def get_schema(tables: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Return the schema markdown keyed by view name + a combined block.

    ``tables`` is an optional comma-separated list of view names to filter.
    The combined block (``combined``) folds in cross-datasource join hints
    so multi-CSV setups still get join candidates surfaced to the LLM.
    """
    registry = get_registry()
    schema_by_view: Dict[str, str] = {}
    for record in registry.list_datasources():
        if not record.schema_markdown:
            continue
        for view_name in record.view_names:
            schema_by_view[view_name] = record.schema_markdown

    requested_views: Optional[List[str]] = None
    if tables:
        requested_views = [t.strip() for t in tables.split(",") if t.strip()]
        schema_by_view = {k: v for k, v in schema_by_view.items() if k in requested_views}

    combined = registry.aggregate_schema_markdown(view_names=requested_views)

    # Collect context summaries from included datasources
    context_parts: List[str] = []
    for record in registry.list_datasources():
        if record.context_summary:
            if requested_views is None or any(v in requested_views for v in record.view_names):
                context_parts.append(record.context_summary)

    return {
        "schema": schema_by_view,
        "combined": combined,
        "context": "\n\n".join(context_parts) if context_parts else "",
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
