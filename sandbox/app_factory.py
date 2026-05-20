"""FastAPI application factory and lifecycle hooks."""
from __future__ import annotations

import infrastructure.matplotlib_backend  # noqa: F401  (must run before pyplot imports)

from fastapi import FastAPI

from api.routes import datasources, execution, system
from datasources.bootstrap import bootstrap_from_app
from infrastructure.duckdb import shutdown as duckdb_shutdown
from infrastructure.duckdb import startup as duckdb_startup
from infrastructure.logging_setup import configure_logging


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="Data Analytics Sandbox", version="2.0.0")

    app.include_router(datasources.router)
    app.include_router(execution.router)
    app.include_router(system.router)

    @app.on_event("startup")
    async def open_duckdb() -> None:
        await duckdb_startup()

    @app.on_event("shutdown")
    async def close_duckdb() -> None:
        await duckdb_shutdown()

    @app.on_event("startup")
    async def bootstrap_datasources() -> None:
        await bootstrap_from_app()

    return app
