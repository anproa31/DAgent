"""Datasource management API.

Replaces the legacy "convert everything to PostgreSQL" upload endpoints
with a unified datasource registry that supports files (CSV, Excel,
SQLite, Parquet) and live database connections (PostgreSQL, MySQL, ...).
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from ..datasource_registry import get_registry
from ..models.datasource import (
    CreateDatabaseDatasourceRequest,
    CreateFileDatasourceResponse,
    DatasourceListResponse,
    DatasourceRecord,
    DeleteDatasourceResponse,
)
from ..models.responses import ConnectionResponse
from ..utils.prompts import set_db_schema

router = APIRouter()


SANDBOX_URL = os.getenv("CODE_RUNNER_URL", "http://sandbox:8001/").rstrip("/")
PREVIEW_SESSION_ID = "__preview__"


# ---------------------------------------------------------------------------
# Unified datasource endpoints
# ---------------------------------------------------------------------------


@router.get("/api/datasources", response_model=DatasourceListResponse)
async def list_datasources() -> DatasourceListResponse:
    """List every registered datasource with its schema metadata."""
    registry = get_registry()
    return DatasourceListResponse(datasources=registry.list_datasources())


@router.post("/api/datasources/upload", response_model=CreateFileDatasourceResponse)
async def upload_datasource_files(
    files: List[UploadFile] = File(...),
) -> CreateFileDatasourceResponse:
    """Upload one or more file-based datasources (CSV/Excel/SQLite/Parquet)."""
    registry = get_registry()
    created: List[DatasourceRecord] = []
    for file in files:
        record = await registry.add_file_datasource(file)
        created.append(record)

    set_db_schema()
    return CreateFileDatasourceResponse(
        datasources=created,
        message=f"Registered {len(created)} datasource(s)",
    )


@router.post("/api/datasources/resync")
async def resync_datasources() -> Dict[str, Any]:
    """Force the sandbox to re-apply every datasource's DDL.

    Useful when the sandbox was restarted independently of the app (e.g.
    after editing sandbox code under ``uvicorn --reload``) and the user
    notices queries failing with ``Table ... does not exist``.
    """
    registry = get_registry()
    resynced: List[str] = []
    failed: List[Dict[str, str]] = []
    for record, snippets in registry.rebuild_all_views_snippets():
        error = await registry.notify_sandbox_register(record, snippets)
        if error:
            failed.append({"id": record.id, "name": record.name, "error": error})
        else:
            resynced.append(record.id)
    set_db_schema()
    return {
        "resynced": resynced,
        "failed": failed,
        "message": f"Resynced {len(resynced)} datasource(s); {len(failed)} failed.",
    }


@router.post("/api/datasources/connect", response_model=DatasourceRecord)
async def connect_datasource(payload: CreateDatabaseDatasourceRequest) -> DatasourceRecord:
    """Register a remote database datasource."""
    registry = get_registry()
    record = await registry.add_database_datasource(
        name=payload.name,
        db_type=payload.type,
        host=payload.host,
        port=payload.port,
        database=payload.database,
        user=payload.user,
        password=payload.password,
        additional_properties=payload.additional_properties,
        connection_string=payload.connection_string,
    )
    set_db_schema()
    return record


@router.delete("/api/datasources/{datasource_id}", response_model=DeleteDatasourceResponse)
async def delete_datasource(datasource_id: str) -> DeleteDatasourceResponse:
    registry = get_registry()
    if not await registry.delete_datasource(datasource_id):
        raise HTTPException(status_code=404, detail="Datasource not found")
    set_db_schema()
    return DeleteDatasourceResponse(success=True, deleted_id=datasource_id)


# ---------------------------------------------------------------------------
# Compatibility aliases
# ---------------------------------------------------------------------------
# The frontend still talks to ``/api/get-table-list``, ``/api/upload-csv-xlsx``,
# ``/api/upload-sqlite-db`` and ``/api/connect-external-postgres``. These
# shims keep the UI working while the multi-datasource refactor lands; they
# all delegate to the new registry.


@router.get("/api/get-table-list", response_model=ConnectionResponse)
async def get_table_list() -> ConnectionResponse:
    registry = get_registry()
    view_names = registry.all_view_names()
    return ConnectionResponse(
        table_count=len(view_names),
        table_names=view_names,
        message="Successfully retrieved tables from the datasource registry",
    )


@router.post("/api/upload-csv-xlsx", response_model=ConnectionResponse)
async def upload_csv_xlsx(files: List[UploadFile] = File(...)) -> ConnectionResponse:
    registry = get_registry()
    created_views: List[str] = []
    for file in files:
        record = await registry.add_file_datasource(file)
        created_views.extend(record.view_names)
    set_db_schema()
    return ConnectionResponse(
        table_count=len(created_views),
        table_names=created_views,
        message="Files uploaded and registered as datasources",
    )


@router.post("/api/upload-sqlite-db", response_model=ConnectionResponse)
async def upload_sqlite_db(file: UploadFile = File(...)) -> ConnectionResponse:
    registry = get_registry()
    record = await registry.add_file_datasource(file)
    set_db_schema()
    return ConnectionResponse(
        table_count=len(record.view_names),
        table_names=record.view_names,
        message="SQLite file registered as a datasource",
    )


@router.post("/api/connect-external-postgres", response_model=ConnectionResponse)
async def connect_external_postgres(connection_string: str = Form(...)) -> ConnectionResponse:
    from ..models.datasource import DatasourceDatabaseType

    registry = get_registry()
    record = await registry.add_database_datasource(
        name="external_postgres",
        db_type=DatasourceDatabaseType.POSTGRES,
        connection_string=connection_string,
    )
    set_db_schema()
    return ConnectionResponse(
        table_count=len(record.view_names),
        table_names=record.view_names,
        message=f"Connected to external PostgreSQL and registered {len(record.view_names)} view(s)",
    )


@router.delete("/api/delete-table/{view_name}")
async def delete_table(view_name: str):
    """Compatibility shim: delete the datasource that owns ``view_name``."""
    registry = get_registry()
    for record in registry.list_datasources():
        if view_name in record.view_names:
            await registry.delete_datasource(record.id)
            set_db_schema()
            return {"message": f"Datasource for view '{view_name}' deleted"}
    raise HTTPException(status_code=404, detail=f"View '{view_name}' not found")


# ---------------------------------------------------------------------------
# Table preview proxy (frontend table preview page)
# ---------------------------------------------------------------------------


def _validate_view_name(view_name: str) -> None:
    registry = get_registry()
    if view_name not in registry.all_view_names():
        raise HTTPException(status_code=404, detail=f"View '{view_name}' not found")


def _safe_quote_identifier(identifier: str) -> str:
    """Quote a DuckDB identifier. Identifier is validated against the registry."""
    return '"' + identifier.replace('"', '""') + '"'


async def _run_preview_sql(sql: str, preview_limit: int = 20) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{SANDBOX_URL}/sql",
            json={
                "sql": sql,
                "id": PREVIEW_SESSION_ID,
                "result_variable": "_preview_df",
                "preview_limit": preview_limit,
            },
        )
    payload = response.json()
    if response.status_code != 200 or "error" in payload:
        raise HTTPException(
            status_code=400,
            detail=payload.get("error") or f"Preview failed (status {response.status_code})",
        )
    return payload


@router.get("/api/table-data/{view_name}")
async def get_table_data(
    view_name: str,
    limit: int = Query(100, ge=1, le=10_000),
    offset: int = Query(0, ge=0),
    sort_column: Optional[str] = None,
    sort_direction: Optional[str] = None,
    filter_column: Optional[str] = None,
    filter_value: Optional[str] = None,
) -> Dict[str, Any]:
    """Preview rows for a registered view by proxying SQL to the sandbox.

    All identifier inputs (``view_name``, ``sort_column``, ``filter_column``)
    are validated against the registry/sandbox schema so SQL injection via
    column names is not possible.
    """
    _validate_view_name(view_name)
    safe_view = _safe_quote_identifier(view_name)

    # Look up the column list for the view so we can validate sort/filter inputs.
    columns_payload = await _run_preview_sql(
        f"SELECT * FROM {safe_view} LIMIT 0"
    )
    valid_columns = set(columns_payload.get("columns", []))

    where_clause = ""
    if filter_column and filter_value is not None:
        if filter_column not in valid_columns:
            raise HTTPException(
                status_code=400, detail=f"Invalid filter column: {filter_column}"
            )
        safe_col = _safe_quote_identifier(filter_column)
        escaped = filter_value.replace("'", "''")
        where_clause = f" WHERE CAST({safe_col} AS VARCHAR) ILIKE '%{escaped}%'"

    order_clause = ""
    if sort_column:
        if sort_column not in valid_columns:
            raise HTTPException(
                status_code=400, detail=f"Invalid sort column: {sort_column}"
            )
        direction = (sort_direction or "asc").lower()
        if direction not in ("asc", "desc"):
            raise HTTPException(
                status_code=400, detail=f"Invalid sort direction: {sort_direction}"
            )
        safe_col = _safe_quote_identifier(sort_column)
        order_clause = f" ORDER BY {safe_col} {direction.upper()}"

    count_sql = f"SELECT COUNT(*) AS total FROM {safe_view}{where_clause}"
    count_payload = await _run_preview_sql(count_sql, preview_limit=1)
    total_rows = int(count_payload["preview"][0]["total"]) if count_payload.get("preview") else 0

    data_sql = (
        f"SELECT * FROM {safe_view}{where_clause}{order_clause} "
        f"LIMIT {int(limit)} OFFSET {int(offset)}"
    )
    data_payload = await _run_preview_sql(data_sql, preview_limit=int(limit))

    columns: List[str] = data_payload.get("columns", [])
    preview = data_payload.get("preview", [])
    return {
        "table_name": view_name,
        "columns": columns,
        "data": preview,
        "total_rows": total_rows,
        "preview_rows": len(preview),
        "sort_column": sort_column,
        "sort_direction": sort_direction,
        "filter_column": filter_column,
        "filter_value": filter_value,
    }
