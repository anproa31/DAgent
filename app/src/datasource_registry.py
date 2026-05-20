"""Datasource registry: persistent metadata + sandbox synchronisation."""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, UploadFile

from .core.config import get_settings
from .dce_introspection import (
    IntrospectionOutcome,
    introspect_database_datasource,
    introspect_file_datasource,
    parse_connection_string,
)
from .infrastructure.external.context_engine_client import ContextEngineClient
from .infrastructure.external.sandbox_client import SandboxClient
from .infrastructure.persistence.datasource_repository import DatasourceRepository
from .models.datasource import (
    DatasourceDatabaseType,
    DatasourceFileType,
    DatasourceKind,
    DatasourceRecord,
    DatasourceTableInfo,
)

logger = logging.getLogger(__name__)

_EXTENSION_MAP: Dict[str, DatasourceFileType] = {
    ".csv": DatasourceFileType.CSV,
    ".tsv": DatasourceFileType.CSV,
    ".xlsx": DatasourceFileType.EXCEL,
    ".xls": DatasourceFileType.EXCEL,
    ".db": DatasourceFileType.SQLITE,
    ".sqlite": DatasourceFileType.SQLITE,
    ".sqlite3": DatasourceFileType.SQLITE,
    ".parquet": DatasourceFileType.PARQUET,
}


def _extract_columns_from_markdown(markdown: str, view_name: str) -> List[str]:
    if not markdown:
        return []

    columns: List[str] = []
    in_block = False
    seen_header = False
    for line in markdown.splitlines():
        stripped = line.strip()
        if stripped.startswith("## Table:"):
            in_block = stripped.endswith(view_name) or stripped.endswith(f"Table: {view_name}")
            seen_header = False
            continue
        if not in_block:
            continue
        if stripped.startswith("**") or not stripped:
            in_block = False
            continue
        if not stripped.startswith("|"):
            continue
        if not seen_header:
            seen_header = True
            continue
        if re.match(r"^\|\s*-+", stripped):
            continue
        cell = stripped.split("|")[1].strip()
        if cell:
            columns.append(cell)
    return columns


def detect_file_type(filename: str) -> DatasourceFileType:
    suffix = Path(filename).suffix.lower()
    if suffix not in _EXTENSION_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{suffix}'. Supported: {sorted(_EXTENSION_MAP)}",
        )
    return _EXTENSION_MAP[suffix]


class DatasourceRegistry:
    """Thread-safe datasource registry backed by JSON persistence."""

    def __init__(
        self,
        repository: Optional[DatasourceRepository] = None,
        sandbox: Optional[SandboxClient] = None,
        context_engine: Optional[ContextEngineClient] = None,
    ) -> None:
        self._repo = repository or DatasourceRepository()
        self._sandbox = sandbox or SandboxClient()
        self._context_engine = context_engine or ContextEngineClient()
        self._lock = threading.RLock()

    def list_datasources(self) -> List[DatasourceRecord]:
        return self._repo.list_all()

    def get_datasource(self, datasource_id: str) -> Optional[DatasourceRecord]:
        return self._repo.get(datasource_id)

    def all_view_names(self) -> List[str]:
        return [v for rec in self._repo.list_all() for v in rec.view_names]

    async def add_file_datasource(self, upload: UploadFile) -> DatasourceRecord:
        if not upload.filename:
            raise HTTPException(status_code=400, detail="Uploaded file has no filename")

        file_type = detect_file_type(upload.filename)
        datasource_id = str(uuid.uuid4())
        ds_dir = os.path.join(self._repo.files_dir, datasource_id)
        os.makedirs(ds_dir, exist_ok=True)
        stored_path = os.path.join(ds_dir, upload.filename)

        try:
            with open(stored_path, "wb") as out:
                while True:
                    chunk = await upload.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
        except Exception:
            shutil.rmtree(ds_dir, ignore_errors=True)
            raise

        try:
            outcome = introspect_file_datasource(
                name=Path(upload.filename).stem,
                file_type=file_type.value,
                file_path=stored_path,
            )
        except Exception as exc:
            shutil.rmtree(ds_dir, ignore_errors=True)
            raise HTTPException(status_code=400, detail=f"Introspection failed: {exc}") from exc

        outcome.context_markdown = await self._context_engine.build_context(
            Path(upload.filename).stem, outcome
        )

        record = self._build_record(
            datasource_id=datasource_id,
            name=Path(upload.filename).stem,
            kind=DatasourceKind.FILE,
            type_value=file_type.value,
            config={"path": stored_path, "original_filename": upload.filename},
            outcome=outcome,
        )
        self._repo.save(record)

        sync_error = await self._notify_sandbox_register(record, outcome.sql_snippets)
        if sync_error:
            self._mark_sync_error(record.id, sync_error)
            record.error = sync_error
        return record

    async def add_database_datasource(
        self,
        *,
        name: str,
        db_type: DatasourceDatabaseType,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        additional_properties: Optional[Dict[str, Any]] = None,
        connection_string: Optional[str] = None,
    ) -> DatasourceRecord:
        config: Dict[str, Any] = {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
            "additional_properties": additional_properties or {},
        }
        if connection_string:
            parsed = parse_connection_string(connection_string)
            for key, value in parsed.items():
                if config.get(key) in (None, "") and value is not None:
                    config[key] = value
        config = {k: v for k, v in config.items() if v is not None}

        try:
            outcome = introspect_database_datasource(
                name=name, db_type=db_type.value, config=config
            )
        except Exception as exc:
            raise HTTPException(
                status_code=400, detail=f"Connection or introspection failed: {exc}"
            ) from exc

        outcome.context_markdown = await self._context_engine.build_context(name, outcome)

        record = self._build_record(
            datasource_id=str(uuid.uuid4()),
            name=name,
            kind=DatasourceKind.DATABASE,
            type_value=db_type.value,
            config=config,
            outcome=outcome,
        )
        self._repo.save(record)

        sync_error = await self._notify_sandbox_register(record, outcome.sql_snippets)
        if sync_error:
            self._mark_sync_error(record.id, sync_error)
            record.error = sync_error
        return record

    async def delete_datasource(self, datasource_id: str) -> bool:
        record = self._repo.delete(datasource_id)
        if record is None:
            return False

        if record.kind == DatasourceKind.FILE:
            try:
                stored_path = record.config.get("path")
                if stored_path:
                    parent_dir = os.path.dirname(stored_path)
                    if parent_dir.startswith(self._repo.files_dir):
                        shutil.rmtree(parent_dir, ignore_errors=True)
            except Exception as exc:
                logger.warning("Failed to remove files for %s: %s", datasource_id, exc)

        try:
            await self._sandbox.unregister_datasource(record.id, record.view_names)
        except Exception as exc:
            logger.warning("Sandbox unregister failed for %s: %s", record.id, exc)
        return True

    def rebuild_all_views_snippets(self) -> List[Tuple[DatasourceRecord, List[str]]]:
        rebuilt: List[Tuple[DatasourceRecord, List[str]]] = []
        dirty = False
        for record in self._repo.list_all():
            try:
                outcome = self._reintrospect(record)
            except Exception as exc:
                logger.warning("Failed to rebuild snippets for %s: %s", record.id, exc)
                continue

            new_tables = [
                DatasourceTableInfo(
                    name=tbl.name,
                    column_count=len(tbl.columns),
                    row_count=tbl.row_count,
                    description=tbl.description,
                )
                for tbl in outcome.tables
            ]
            schema_changed = (
                record.schema_markdown != outcome.schema_markdown
                or record.view_names != outcome.view_names
            )
            if schema_changed:
                self._repo.update(
                    record.id,
                    schema_markdown=outcome.schema_markdown,
                    view_names=outcome.view_names,
                    tables=new_tables,
                )
                record = self._repo.get(record.id) or record
                dirty = True

            rebuilt.append((record, outcome.sql_snippets))

        if dirty:
            pass  # updates already persisted via _repo.update
        return rebuilt

    async def notify_sandbox_register(
        self,
        record: DatasourceRecord,
        sql_snippets: List[str],
        *,
        retries: int = 5,
        backoff_seconds: float = 1.5,
    ) -> Optional[str]:
        return await self._notify_sandbox_register(
            record, sql_snippets, retries=retries, backoff_seconds=backoff_seconds
        )

    def aggregate_schema_markdown(self, view_names: Optional[List[str]] = None) -> str:
        records = self._repo.list_all()
        included_views: set[str] = set()
        parts: List[str] = []
        for record in records:
            if view_names is None:
                if record.context_summary:
                    parts.append(record.context_summary)
                parts.append(f"# Datasource: {record.name} ({record.type})")
                if record.schema_markdown:
                    parts.append(record.schema_markdown)
                included_views.update(record.view_names)
                continue

            relevant = [v for v in record.view_names if v in view_names]
            if not relevant:
                continue
            if record.context_summary:
                parts.append(record.context_summary)
            parts.append(f"# Datasource: {record.name} ({record.type})")
            if record.schema_markdown:
                parts.append(record.schema_markdown)
            included_views.update(record.view_names)

        cross_hints = self._cross_datasource_join_hints(included_views)
        if cross_hints:
            parts.append("# Cross-datasource join candidates")
            parts.append(
                "Columns sharing a name across multiple views — likely join keys:"
            )
            parts.extend(cross_hints)

        return "\n\n".join(parts)

    def _build_record(
        self,
        *,
        datasource_id: str,
        name: str,
        kind: DatasourceKind,
        type_value: str,
        config: Dict[str, Any],
        outcome: IntrospectionOutcome,
    ) -> DatasourceRecord:
        tables = [
            DatasourceTableInfo(
                name=tbl.name,
                column_count=len(tbl.columns),
                row_count=tbl.row_count,
                description=tbl.description,
            )
            for tbl in outcome.tables
        ]
        return DatasourceRecord(
            id=datasource_id,
            name=name,
            kind=kind,
            type=type_value,
            config=config,
            view_names=outcome.view_names,
            tables=tables,
            schema_markdown=outcome.schema_markdown,
            context_summary=outcome.context_markdown,
            created_at=datetime.utcnow(),
        )

    def _reintrospect(self, record: DatasourceRecord) -> IntrospectionOutcome:
        if record.kind == DatasourceKind.FILE:
            return introspect_file_datasource(
                name=record.name,
                file_type=record.type,
                file_path=record.config["path"],
            )
        return introspect_database_datasource(
            name=record.name, db_type=record.type, config=record.config
        )

    async def _notify_sandbox_register(
        self,
        record: DatasourceRecord,
        sql_snippets: List[str],
        *,
        retries: int = 5,
        backoff_seconds: float = 1.5,
    ) -> Optional[str]:
        payload = self._build_register_payload(record, sql_snippets)
        last_error: Optional[str] = None
        for attempt in range(1, retries + 1):
            try:
                await self._sandbox.register_datasource(payload)
                return None
            except Exception as exc:
                last_error = str(exc)
                logger.info(
                    "Sandbox sync attempt %d/%d failed for %s: %s",
                    attempt,
                    retries,
                    record.id,
                    exc,
                )
                if attempt < retries:
                    await asyncio.sleep(backoff_seconds * attempt)

        logger.warning(
            "Sandbox sync failed for %s after %d attempts: %s",
            record.id,
            retries,
            last_error,
        )
        return last_error

    def _mark_sync_error(self, datasource_id: str, error: str) -> None:
        record = self._repo.get(datasource_id)
        if record is None:
            return
        record.error = error
        self._repo.save(record)

    def _build_register_payload(
        self, record: DatasourceRecord, sql_snippets: List[str]
    ) -> Dict[str, Any]:
        return {
            "datasource_id": record.id,
            "name": record.name,
            "kind": record.kind.value,
            "type": record.type,
            "view_names": record.view_names,
            "config": record.config,
            "sql_snippets": sql_snippets,
        }

    def _cross_datasource_join_hints(self, included_views: set[str]) -> List[str]:
        if not included_views:
            return []

        col_to_views: Dict[str, set[str]] = {}
        for record in self._repo.list_all():
            for table_info in record.tables:
                if table_info.name not in included_views:
                    continue
                for col in _extract_columns_from_markdown(
                    record.schema_markdown, table_info.name
                ):
                    col_to_views.setdefault(col.lower(), set()).add(table_info.name)

        hints: List[str] = []
        for col, view_set in sorted(col_to_views.items()):
            if len(view_set) >= 2:
                views_str = ", ".join(f"`{v}`" for v in sorted(view_set))
                hints.append(f"- `{col}` appears in {views_str}")
        return hints


_registry: Optional[DatasourceRegistry] = None
_registry_lock = threading.Lock()


def get_registry() -> DatasourceRegistry:
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = DatasourceRegistry()
    return _registry


def reset_registry() -> None:
    """Reset singleton registry (used in tests)."""
    global _registry
    with _registry_lock:
        _registry = None


# Backward-compatible module-level constants
_settings = get_settings()
DATASOURCE_ROOT = _settings.datasource_root
REGISTRY_PATH = _settings.registry_path
FILES_DIR = _settings.files_dir
CODE_RUNNER_URL = _settings.code_runner_url
CONTEXT_ENGINE_URL = _settings.context_engine_url
