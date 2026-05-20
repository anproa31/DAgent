"""Health and status endpoints."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from datasources import registry
from execution import session

router = APIRouter(tags=["system"])


@router.get("/status")
def get_status() -> Dict[str, Any]:
    return {
        "que": session.queue_depth(),
        "datasource_count": registry.count(),
        "view_count": registry.total_view_count(),
    }


@router.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "service": "sandbox", "duckdb": True}
