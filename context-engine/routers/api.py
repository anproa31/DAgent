"""API routes for the context engine microservice."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from context_engine.engine import build_context, enhance_for_query
from context_engine.models import BuildRequest, BuildResponse, EnhanceRequest, EnhanceResponse, HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse()


@router.post("/build", response_model=BuildResponse)
async def build(req: BuildRequest):
    """Build semantic context from raw introspection data."""
    try:
        tables_payload = [
            {
                "name": t.name,
                "columns": [{"name": c.name, "type": c.type, "nullable": c.nullable} for c in t.columns],
                "row_count": t.row_count,
                "samples": t.samples,
                "column_stats": {
                    k: {
                        "distinct_count": v.distinct_count,
                        "null_count": v.null_count,
                        "min_value": v.min_value,
                        "max_value": v.max_value,
                        "top_values": v.top_values,
                    }
                    for k, v in t.column_stats.items()
                },
            }
            for t in req.tables
        ]

        ctx = build_context(req.datasource_name, tables_payload)

        return BuildResponse(
            context_summary=ctx.context_markdown,
            domain=ctx.domain,
            table_grains=ctx.table_grains,
            query_capabilities=ctx.capabilities,
        )
    except Exception as exc:
        logger.error("Context build failed for %s: %s", req.datasource_name, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Context build failed: {exc}")


@router.post("/enhance", response_model=EnhanceResponse)
async def enhance(req: EnhanceRequest):
    """Filter context to be query-relevant."""
    try:
        enhanced = enhance_for_query(req.context_summary, req.query)
        return EnhanceResponse(enhanced_context=enhanced)
    except Exception as exc:
        logger.error("Context enhancement failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Context enhancement failed: {exc}")
