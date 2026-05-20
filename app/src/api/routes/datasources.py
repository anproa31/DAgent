"""Datasource management API routes."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from ...application.services.prompt_service import PromptService
from ...datasource_registry import DatasourceRegistry
from ...infrastructure.external.sandbox_client import SandboxClient
from ...models.datasource import (
    CreateDatabaseDatasourceRequest,
    CreateFileDatasourceResponse,
    DatasourceListResponse,
    DatasourceRecord,
    DeleteDatasourceResponse,
)
from ...models.responses import ConnectionResponse
from ..dependencies.services import get_datasource_registry, get_prompt_service_dep

router = APIRouter(tags=["datasources"])

PREVIEW_SESSION_ID = "__preview__"


def _get_sandbox() -> SandboxClient:
    return SandboxClient()


@router.get("/api/datasources", response_model=DatasourceListResponse)
async def list_datasources(
    registry: DatasourceRegistry = Depends(get_datasource_registry),
) -> DatasourceListResponse:
    return DatasourceListResponse(datasources=registry.list_datasources())


@router.post("/api/datasources/upload", response_model=CreateFileDatasourceResponse)
async def upload_datasource_files(
    files: List[UploadFile] = File(...),
    registry: DatasourceRegistry = Depends(get_datasource_registry),
    prompts: PromptService = Depends(get_prompt_service_dep),
) -> CreateFileDatasourceResponse:
    created: List[DatasourceRecord] = []
    for file in files:
        record = await registry.add_file_datasource(file)
        created.append(record)
    prompts.refresh_schema_cache()
    return CreateFileDatasourceResponse(
        datasources=created,
        message=f"Registered {len(created)} datasource(s)",
    )


@router.post("/api/datasources/resync")
async def resync_datasources(
    registry: DatasourceRegistry = Depends(get_datasource_registry),
    prompts: PromptService = Depends(get_prompt_service_dep),
) -> Dict[str, Any]:
    resynced: List[str] = []
    failed: List[Dict[str, str]] = []
    for record, snippets in registry.rebuild_all_views_snippets():
        error = await registry.notify_sandbox_register(record, snippets)
        if error:
            failed.append({"id": record.id, "name": record.name, "error": error})
        else:
            resynced.append(record.id)
    prompts.refresh_schema_cache()
    return {
        "resynced": resynced,
        "failed": failed,
        "message": f"Resynced {len(resynced)} datasource(s); {len(failed)} failed.",
    }


@router.post("/api/datasources/connect", response_model=DatasourceRecord)
async def connect_datasource(
    payload: CreateDatabaseDatasourceRequest,
    registry: DatasourceRegistry = Depends(get_datasource_registry),
    prompts: PromptService = Depends(get_prompt_service_dep),
) -> DatasourceRecord:
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
    prompts.refresh_schema_cache()
    return record


@router.delete("/api/datasources/{datasource_id}", response_model=DeleteDatasourceResponse)
async def delete_datasource(
    datasource_id: str,
    registry: DatasourceRegistry = Depends(get_datasource_registry),
    prompts: PromptService = Depends(get_prompt_service_dep),
) -> DeleteDatasourceResponse:
    if not await registry.delete_datasource(datasource_id):
        raise HTTPException(status_code=404, detail="Datasource not found")
    prompts.refresh_schema_cache()
    return DeleteDatasourceResponse(success=True, deleted_id=datasource_id)


@router.get("/api/get-table-list", response_model=ConnectionResponse)
async def get_table_list(
    registry: DatasourceRegistry = Depends(get_datasource_registry),
) -> ConnectionResponse:
    view_names = registry.all_view_names()
    return ConnectionResponse(
        table_count=len(view_names),
        table_names=view_names,
        message="Successfully retrieved tables from the datasource registry",
    )


@router.post("/api/upload-csv-xlsx", response_model=ConnectionResponse)
async def upload_csv_xlsx(
    files: List[UploadFile] = File(...),
    registry: DatasourceRegistry = Depends(get_datasource_registry),
    prompts: PromptService = Depends(get_prompt_service_dep),
) -> ConnectionResponse:
    created_views: List[str] = []
    for file in files:
        record = await registry.add_file_datasource(file)
        created_views.extend(record.view_names)
    prompts.refresh_schema_cache()
    return ConnectionResponse(
        table_count=len(created_views),
        table_names=created_views,
        message="Files uploaded and registered as datasources",
    )


@router.post("/api/upload-sqlite-db", response_model=ConnectionResponse)
async def upload_sqlite_db(
    file: UploadFile = File(...),
    registry: DatasourceRegistry = Depends(get_datasource_registry),
    prompts: PromptService = Depends(get_prompt_service_dep),
) -> ConnectionResponse:
    record = await registry.add_file_datasource(file)
    prompts.refresh_schema_cache()
    return ConnectionResponse(
        table_count=len(record.view_names),
        table_names=record.view_names,
        message="SQLite file registered as a datasource",
    )


@router.post("/api/connect-external-postgres", response_model=ConnectionResponse)
async def connect_external_postgres(
    connection_string: str = Form(...),
    registry: DatasourceRegistry = Depends(get_datasource_registry),
    prompts: PromptService = Depends(get_prompt_service_dep),
) -> ConnectionResponse:
    from ...models.datasource import DatasourceDatabaseType

    record = await registry.add_database_datasource(
        name="external_postgres",
        db_type=DatasourceDatabaseType.POSTGRES,
        connection_string=connection_string,
    )
    prompts.refresh_schema_cache()
    return ConnectionResponse(
        table_count=len(record.view_names),
        table_names=record.view_names,
        message=(
            f"Connected to external PostgreSQL and registered "
            f"{len(record.view_names)} view(s)"
        ),
    )


@router.delete("/api/delete-table/{view_name}")
async def delete_table(
    view_name: str,
    registry: DatasourceRegistry = Depends(get_datasource_registry),
    prompts: PromptService = Depends(get_prompt_service_dep),
):
    for record in registry.list_datasources():
        if view_name in record.view_names:
            await registry.delete_datasource(record.id)
            prompts.refresh_schema_cache()
            return {"message": f"Datasource for view '{view_name}' deleted"}
    raise HTTPException(status_code=404, detail=f"View '{view_name}' not found")


def _validate_view_name(registry: DatasourceRegistry, view_name: str) -> None:
    if view_name not in registry.all_view_names():
        raise HTTPException(status_code=404, detail=f"View '{view_name}' not found")


def _safe_quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


async def _run_preview_sql(
    sandbox: SandboxClient, sql: str, preview_limit: int = 20
) -> Dict[str, Any]:
    payload = await sandbox.run_sql(
        sql, PREVIEW_SESSION_ID, preview_limit=preview_limit
    )
    if "error" in payload:
        raise HTTPException(status_code=400, detail=payload.get("error"))
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
    registry: DatasourceRegistry = Depends(get_datasource_registry),
):
    sandbox = _get_sandbox()
    _validate_view_name(registry, view_name)
    safe_view = _safe_quote_identifier(view_name)

    columns_payload = await _run_preview_sql(
        sandbox, f"SELECT * FROM {safe_view} LIMIT 0"
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
    count_payload = await _run_preview_sql(sandbox, count_sql, preview_limit=1)
    total_rows = (
        int(count_payload["preview"][0]["total"]) if count_payload.get("preview") else 0
    )

    data_sql = (
        f"SELECT * FROM {safe_view}{where_clause}{order_clause} "
        f"LIMIT {int(limit)} OFFSET {int(offset)}"
    )
    data_payload = await _run_preview_sql(sandbox, data_sql, preview_limit=int(limit))

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
