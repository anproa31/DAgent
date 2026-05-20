"""Internal endpoints consumed by sister services (agent-service, sandbox)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from ...datasource_registry import DatasourceRegistry
from ..dependencies.services import get_datasource_registry

router = APIRouter(prefix="/internal", tags=["internal"])


@router.get("/schema")
async def get_schema(
    tables: Optional[str] = Query(None),
    registry: DatasourceRegistry = Depends(get_datasource_registry),
) -> Dict[str, Any]:
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
async def get_datasources(
    registry: DatasourceRegistry = Depends(get_datasource_registry),
) -> Dict[str, Any]:
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
async def sandbox_bootstrap(
    registry: DatasourceRegistry = Depends(get_datasource_registry),
) -> Dict[str, Any]:
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
