"""Internal endpoints consumed by sister services (agent-service, sandbox)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ...datasource_registry import DatasourceRegistry
from ...models.datasource import (
    DiscoverWebDataRequest,
    DiscoverWebDataResponse,
    RegisterWebDataRequest,
    WebDiscoverCandidate,
)
from ...application.services.web_discover_service import WebDiscoverService
from ..dependencies.services import get_datasource_registry, get_web_discover_service

router = APIRouter(prefix="/internal", tags=["internal"])


def _discover_response(outcome, *, message: str) -> DiscoverWebDataResponse:
    return DiscoverWebDataResponse(
        query=outcome.query,
        search_count=outcome.search_count,
        candidates=[
            WebDiscoverCandidate(
                title=c.title,
                url=c.url,
                snippet=c.snippet,
                score=c.score,
                reason=c.reason,
            )
            for c in outcome.candidates
        ],
        selected_urls=outcome.selected_urls,
        datasources=outcome.datasources,
        errors=outcome.errors,
        message=message,
    )


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


@router.post("/web/propose", response_model=DiscoverWebDataResponse)
async def internal_propose_web_data(
    payload: DiscoverWebDataRequest,
    discover: WebDiscoverService = Depends(get_web_discover_service),
) -> DiscoverWebDataResponse:
    """Search/rank dataset URLs without registering (for HITL approval)."""
    outcome = await discover.propose(
        payload.query,
        model=payload.model,
        base_url=payload.base_url,
        api_key=payload.api_key,
        direct_url=payload.url,
        max_fetch_attempts=payload.max_results,
    )
    return _discover_response(
        outcome,
        message=(
            f"Proposed {len(outcome.selected_urls)} dataset URL(s) for approval"
            if outcome.selected_urls
            else "No dataset URLs proposed"
        ),
    )


@router.post("/web/register", response_model=DiscoverWebDataResponse)
async def internal_register_web_data(
    payload: RegisterWebDataRequest,
    discover: WebDiscoverService = Depends(get_web_discover_service),
) -> DiscoverWebDataResponse:
    """Register user-approved dataset URLs."""
    from ...application.services.prompt_service import get_prompt_service

    if not payload.urls:
        raise HTTPException(status_code=400, detail="At least one URL is required")

    outcome = await discover.register_urls(
        payload.urls,
        name=payload.name,
        query=payload.query or "web import",
    )
    if outcome.datasources:
        get_prompt_service().refresh_schema_cache()

    return _discover_response(
        outcome,
        message=(
            f"Registered {len(outcome.datasources)} datasource(s)"
            if outcome.datasources
            else "Registration failed"
        ),
    )


@router.post("/web/discover", response_model=DiscoverWebDataResponse)
async def internal_discover_web_data(
    payload: DiscoverWebDataRequest,
    discover: WebDiscoverService = Depends(get_web_discover_service),
) -> DiscoverWebDataResponse:
    """One-shot discover + register (non-HITL)."""
    from ...application.services.prompt_service import get_prompt_service

    outcome = await discover.discover_and_register(
        payload.query,
        name=payload.name,
        model=payload.model,
        base_url=payload.base_url,
        api_key=payload.api_key,
        direct_url=payload.url,
        max_fetch_attempts=payload.max_results,
    )
    if outcome.datasources:
        get_prompt_service().refresh_schema_cache()

    return _discover_response(
        outcome,
        message=(
            f"Registered {len(outcome.datasources)} datasource(s) from web discovery"
            if outcome.datasources
            else "No datasources registered"
        ),
    )
