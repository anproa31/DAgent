"""Optional /api/v1 route aliases for analysis and model endpoints.

Datasource routes remain at ``/api/datasources/*`` (unchanged for frontend compatibility).
"""
from __future__ import annotations

from fastapi import APIRouter

from .analysis import router as analysis_router
from .health import router as health_router
from .models import router as models_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(health_router)
v1_router.include_router(analysis_router)
v1_router.include_router(models_router)
