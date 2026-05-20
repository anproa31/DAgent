"""Health and status endpoints."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from control_layer import get_control_layer
from datasources import registry

router = APIRouter(tags=["system"])


@router.get("/status")
def get_status() -> Dict[str, Any]:
    control = get_control_layer()
    health = control.runtime_health()
    return {
        "que": control.queue_depth(),
        "datasource_count": registry.count(),
        "view_count": registry.total_view_count(),
        "runtime": health.get("runtime"),
        "active_sessions": health.get("active_sessions"),
    }


@router.get("/health")
def health() -> Dict[str, Any]:
    control = get_control_layer()
    runtime_health = control.runtime_health()
    return {
        "status": runtime_health.get("status", "ok"),
        "service": "sandbox",
        "duckdb": True,
        "runtime": runtime_health,
    }


@router.get("/sessions")
def list_sessions() -> Dict[str, Any]:
    return {"sessions": get_control_layer().list_sessions()}
