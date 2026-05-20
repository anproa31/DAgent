"""Datasource registration HTTP routes."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from api.schemas import RegisterDatasourceRequest, UnregisterDatasourceRequest
from datasources import registry, service
from infrastructure.logging_setup import logger

router = APIRouter(tags=["datasources"])


@router.post("/register-datasource")
def register_datasource(request: RegisterDatasourceRequest) -> Dict[str, Any]:
    try:
        return service.register(request)
    except Exception as exc:
        logger.exception("Failed to register datasource %s", request.datasource_id)
        raise HTTPException(status_code=400, detail=f"Registration failed: {exc}")


@router.post("/unregister-datasource")
def unregister_datasource(request: UnregisterDatasourceRequest) -> Dict[str, Any]:
    return service.unregister(request)


@router.get("/datasources")
def list_datasources() -> Dict[str, Any]:
    return {"datasources": registry.get_all()}
