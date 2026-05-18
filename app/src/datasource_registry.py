"""Datasource registry: persistent metadata + sandbox synchronisation.

Replaces the legacy ``DataService`` that copied every uploaded file into
PostgreSQL. The registry simply records *where the data lives* (path on the
shared volume or remote connection details) and asks DuckDB to introspect
the schema. The sandbox is told to mount the same data via the
``/register-datasource`` endpoint so SQL and Python code can both reach it.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import re

import httpx
from fastapi import HTTPException, UploadFile

from .dce_introspection import (
    IntrospectionOutcome,
    introspect_database_datasource,
    introspect_file_datasource,
    normalize_identifier,
    parse_connection_string,
)


def _extract_columns_from_markdown(markdown: str, view_name: str) -> List[str]:
    """Pull column names out of the per-table markdown block.

    Each table block starts with ``## Table: <name>`` and lists its
    columns in a Markdown table whose first cell is the column name.
    """
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
        # Header row first ("| Column | Type | ..."), then separator ("|---|---|"),
        # then data rows. We want only the data rows' first cell.
        if not seen_header:
            seen_header = True
            continue
        if re.match(r"^\|\s*-+", stripped):
            continue
        cell = stripped.split("|")[1].strip()
        if cell:
            columns.append(cell)
    return columns
from .models.datasource import (
    DatasourceDatabaseType,
    DatasourceFileType,
    DatasourceKind,
    DatasourceRecord,
    DatasourceTableInfo,
)

logger = logging.getLogger(__name__)


DATASOURCE_ROOT = os.environ.get("DATASOURCE_ROOT", "/data/datasources")
REGISTRY_PATH = os.path.join(DATASOURCE_ROOT, "registry.json")
FILES_DIR = os.path.join(DATASOURCE_ROOT, "files")
CODE_RUNNER_URL = os.environ.get("CODE_RUNNER_URL", "http://data-analysis-agent-sandbox:8001/")


# ---------------------------------------------------------------------------
# File-type detection
# ---------------------------------------------------------------------------

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


def detect_file_type(filename: str) -> DatasourceFileType:
    suffix = Path(filename).suffix.lower()
    if suffix not in _EXTENSION_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file extension '{suffix}'. Supported: {sorted(_EXTENSION_MAP)}",
        )
    return _EXTENSION_MAP[suffix]


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@dataclass
class _RegistryState:
    records: Dict[str, DatasourceRecord]


class DatasourceRegistry:
    """Thread-safe in-process registry persisted to ``registry.json``.

    The registry is the single source of truth for *what datasources exist*.
    Schema introspection is delegated to :mod:`dce_introspection`, and the
    sandbox is notified via :meth:`sync_sandbox` so it can mount the same
    DuckDB views.
    """

    def __init__(self, root: str = DATASOURCE_ROOT):
        self._root = root
        self._files_dir = os.path.join(root, "files")
        self._registry_path = os.path.join(root, "registry.json")
        self._lock = threading.RLock()

        os.makedirs(self._files_dir, exist_ok=True)
        self._state = _RegistryState(records=self._load_state())

    # ---- persistence -----------------------------------------------------

    def _load_state(self) -> Dict[str, DatasourceRecord]:
        if not os.path.exists(self._registry_path):
            return {}
        try:
            with open(self._registry_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as exc:
            logger.warning("Failed to load registry file, starting empty: %s", exc)
            return {}

        records: Dict[str, DatasourceRecord] = {}
        for ds_id, payload in raw.items():
            try:
                records[ds_id] = DatasourceRecord(**payload)
            except Exception as exc:
                logger.warning("Skipping invalid registry entry %s: %s", ds_id, exc)
        return records

    def _save_state(self) -> None:
        serialised = {
            ds_id: json.loads(record.model_dump_json())
            for ds_id, record in self._state.records.items()
        }
        tmp = self._registry_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(serialised, f, indent=2, default=str)
        os.replace(tmp, self._registry_path)

    # ---- public API ------------------------------------------------------

    def list_datasources(self) -> List[DatasourceRecord]:
        with self._lock:
            return list(self._state.records.values())

    def get_datasource(self, datasource_id: str) -> Optional[DatasourceRecord]:
        with self._lock:
            return self._state.records.get(datasource_id)

    def all_view_names(self) -> List[str]:
        """Flat list of all DuckDB view names exposed by every datasource."""
        with self._lock:
            return [v for rec in self._state.records.values() for v in rec.view_names]

    async def add_file_datasource(
        self,
        upload: UploadFile,
    ) -> DatasourceRecord:
        """Persist an uploaded file, introspect it, register the metadata."""
        if not upload.filename:
            raise HTTPException(status_code=400, detail="Uploaded file has no filename")

        file_type = detect_file_type(upload.filename)

        datasource_id = str(uuid.uuid4())
        ds_dir = os.path.join(self._files_dir, datasource_id)
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

        record = self._build_record(
            datasource_id=datasource_id,
            name=Path(upload.filename).stem,
            kind=DatasourceKind.FILE,
            type_value=file_type.value,
            config={
                "path": stored_path,
                "original_filename": upload.filename,
            },
            outcome=outcome,
        )

        with self._lock:
            self._state.records[datasource_id] = record
            self._save_state()

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

        # Strip None values from outer config so the introspector sees a clean dict
        config = {k: v for k, v in config.items() if v is not None}

        try:
            outcome = introspect_database_datasource(
                name=name,
                db_type=db_type.value,
                config=config,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Connection or introspection failed: {exc}") from exc

        record = self._build_record(
            datasource_id=str(uuid.uuid4()),
            name=name,
            kind=DatasourceKind.DATABASE,
            type_value=db_type.value,
            config=config,
            outcome=outcome,
        )

        with self._lock:
            self._state.records[record.id] = record
            self._save_state()

        # Block until the sandbox confirms registration: callers expect the
        # view to be queryable on return.
        sync_error = await self._notify_sandbox_register(record, outcome.sql_snippets)
        if sync_error:
            self._mark_sync_error(record.id, sync_error)
            record.error = sync_error

        return record

    async def delete_datasource(self, datasource_id: str) -> bool:
        with self._lock:
            record = self._state.records.pop(datasource_id, None)
            if record is None:
                return False
            self._save_state()

        if record.kind == DatasourceKind.FILE:
            try:
                stored_path = record.config.get("path")
                if stored_path:
                    parent_dir = os.path.dirname(stored_path)
                    if parent_dir.startswith(self._files_dir):
                        shutil.rmtree(parent_dir, ignore_errors=True)
            except Exception as exc:
                logger.warning("Failed to remove files for %s: %s", datasource_id, exc)

        await self._notify_sandbox_unregister(record)
        return True

    def rebuild_all_views_snippets(self) -> List[Tuple[DatasourceRecord, List[str]]]:
        """Re-introspect every datasource and return DDL snippets.

        Used by the sandbox on startup to reconstruct its DuckDB state. The
        original SQL snippets are not persisted in the registry (paths in the
        DDL would go stale on path changes); regenerating them is cheap.

        Side effect: the record's ``schema_markdown`` and ``tables`` are
        refreshed so prompt context picks up any introspector improvements
        (e.g. richer column profiling) without forcing the user to re-upload.
        """
        rebuilt: List[Tuple[DatasourceRecord, List[str]]] = []
        dirty = False
        with self._lock:
            records = list(self._state.records.values())
        for record in records:
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
                with self._lock:
                    live = self._state.records.get(record.id)
                    if live is not None:
                        live.schema_markdown = outcome.schema_markdown
                        live.view_names = outcome.view_names
                        live.tables = new_tables
                        record = live
                dirty = True

            rebuilt.append((record, outcome.sql_snippets))

        if dirty:
            with self._lock:
                self._save_state()
        return rebuilt

    # ---- internals -------------------------------------------------------

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
            name=record.name,
            db_type=record.type,
            config=record.config,
        )

    async def notify_sandbox_register(
        self,
        record: DatasourceRecord,
        sql_snippets: List[str],
        *,
        retries: int = 5,
        backoff_seconds: float = 1.5,
    ) -> Optional[str]:
        """Public wrapper around the registration call. See :meth:`_notify_sandbox_register`."""
        return await self._notify_sandbox_register(
            record, sql_snippets, retries=retries, backoff_seconds=backoff_seconds
        )

    async def _notify_sandbox_register(
        self,
        record: DatasourceRecord,
        sql_snippets: List[str],
        *,
        retries: int = 5,
        backoff_seconds: float = 1.5,
    ) -> Optional[str]:
        """POST the registration payload to the sandbox with exponential-ish retry.

        Returns ``None`` on success, or an error string on failure (after
        exhausting retries). The sandbox may still be starting up while the
        app is already serving uploads, so retrying smooths over that race
        without surfacing a bogus error to the user.
        """
        import asyncio

        payload = self._build_register_payload(record, sql_snippets)
        last_error: Optional[str] = None
        for attempt in range(1, retries + 1):
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.post(
                        CODE_RUNNER_URL.rstrip("/") + "/register-datasource",
                        json=payload,
                    )
                    response.raise_for_status()
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
        """Persist a sync error on the record so the UI/agent can surface it."""
        with self._lock:
            record = self._state.records.get(datasource_id)
            if record is None:
                return
            record.error = error
            self._save_state()

    async def _notify_sandbox_unregister(self, record: DatasourceRecord) -> None:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    CODE_RUNNER_URL.rstrip("/") + "/unregister-datasource",
                    json={"datasource_id": record.id, "view_names": record.view_names},
                )
                response.raise_for_status()
        except Exception as exc:
            logger.warning("Sandbox unregister failed for %s: %s", record.id, exc)

    def _build_register_payload(
        self,
        record: DatasourceRecord,
        sql_snippets: List[str],
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

    def aggregate_schema_markdown(self, view_names: Optional[List[str]] = None) -> str:
        """Concatenated schema markdown for prompts.

        ``view_names`` filters to specific tables/views if provided.
        Cross-datasource join hints are appended at the end so the agent
        can identify likely joins even when each CSV/table lives in its
        own datasource.
        """
        with self._lock:
            records = list(self._state.records.values())

        included_views: set[str] = set()
        parts: List[str] = []
        for record in records:
            if view_names is None:
                parts.append(f"# Datasource: {record.name} ({record.type})")
                if record.schema_markdown:
                    parts.append(record.schema_markdown)
                included_views.update(record.view_names)
                continue

            relevant = [v for v in record.view_names if v in view_names]
            if not relevant:
                continue
            parts.append(f"# Datasource: {record.name} ({record.type})")
            # We currently store one combined markdown per datasource. Filtering
            # by table within a datasource is best-effort: include the whole
            # block if any view matches.
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

    def _cross_datasource_join_hints(self, included_views: set[str]) -> List[str]:
        """Find column names that appear in more than one included view.

        Each schema_markdown block lists columns in a Markdown table whose
        first cell is the column name. We parse that line-by-line to avoid
        introducing a separate column-index field on the record.
        """
        if not included_views:
            return []

        col_to_views: Dict[str, set[str]] = {}
        with self._lock:
            records = list(self._state.records.values())

        for record in records:
            for table_info in record.tables:
                if table_info.name not in included_views:
                    continue
                for col in _extract_columns_from_markdown(record.schema_markdown, table_info.name):
                    col_to_views.setdefault(col.lower(), set()).add(table_info.name)

        hints: List[str] = []
        for col, view_set in sorted(col_to_views.items()):
            if len(view_set) >= 2:
                views_str = ", ".join(f"`{v}`" for v in sorted(view_set))
                hints.append(f"- `{col}` appears in {views_str}")
        return hints


# Module-level singleton — instantiated lazily so the data directory exists.
_registry: Optional[DatasourceRegistry] = None
_registry_lock = threading.Lock()


def get_registry() -> DatasourceRegistry:
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = DatasourceRegistry()
    return _registry
