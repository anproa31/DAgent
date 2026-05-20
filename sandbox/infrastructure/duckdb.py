"""DuckDB connection lifecycle (open on startup, close on shutdown)."""
from __future__ import annotations

from typing import Optional

import duckdb

from infrastructure.config import DUCKDB_PATH
from infrastructure.logging_setup import logger

duckdb_conn: Optional[duckdb.DuckDBPyConnection] = None

_OPTIONAL_EXTENSIONS = ("postgres", "mysql", "sqlite", "excel")


def open_connection() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(DUCKDB_PATH)
    for ext in _OPTIONAL_EXTENSIONS:
        try:
            conn.execute(f"INSTALL {ext}")
            conn.execute(f"LOAD {ext}")
        except Exception as exc:
            logger.info("Optional DuckDB extension %s unavailable: %s", ext, exc)
    return conn


def get_connection() -> duckdb.DuckDBPyConnection:
    """Return the live DuckDB connection (raises if startup hasn't run yet)."""
    if duckdb_conn is None:
        raise RuntimeError("DuckDB connection is not open yet; FastAPI startup hasn't finished.")
    return duckdb_conn


async def startup() -> None:
    """Open the DuckDB file once the worker process starts."""
    global duckdb_conn
    if duckdb_conn is None:
        duckdb_conn = open_connection()
        logger.info("DuckDB connection opened at %s", DUCKDB_PATH)


async def shutdown() -> None:
    """Release the DuckDB file lock so a reloaded worker can grab it again."""
    global duckdb_conn
    if duckdb_conn is not None:
        try:
            duckdb_conn.close()
        finally:
            duckdb_conn = None
            logger.info("DuckDB connection closed")
