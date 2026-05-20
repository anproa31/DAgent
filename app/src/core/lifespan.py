"""Application lifespan hooks."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from ..application.services.prompt_service import get_prompt_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_prompt_service().refresh_schema_cache()
    yield
