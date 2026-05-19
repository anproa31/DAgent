"""Sandbox service: dual-mode Python + SQL executor backed by DuckDB.

Each registered datasource is exposed as a DuckDB view (or attached
database) so SQL queries and pandas code can both target the same data
without copying it into PostgreSQL first. The service keeps per-session
Python locals so models can iterate on partial state, and the DuckDB
connection is shared across sessions so view DDL only has to be applied
once.
"""
from __future__ import annotations

import asyncio
import base64
import io
import json
import logging
import os
import re
import time
import traceback
from typing import Any, Dict, List, Optional

import duckdb
import matplotlib

matplotlib.use("Agg")  # headless backend so plt.Figure works without a display
import matplotlib.pyplot as plt  # noqa: E402  (after backend switch)
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from fastapi import FastAPI, HTTPException  # noqa: E402
from pydantic import BaseModel  # noqa: E402

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Data Analytics Sandbox", version="2.0.0")


# ---------------------------------------------------------------------------
# DuckDB engine + datasource registry mirror
# ---------------------------------------------------------------------------

DUCKDB_PATH = os.environ.get("SANDBOX_DUCKDB_PATH", ":memory:")
DATASOURCE_SYNC_URL = os.environ.get("APP_SERVICE_URL", "http://app:8000").rstrip("/")


def _open_duckdb() -> duckdb.DuckDBPyConnection:
    conn = duckdb.connect(DUCKDB_PATH)
    # Best-effort: pre-install the most commonly needed extensions so the
    # first query against an attached database doesn't slow to a crawl.
    for ext in ("postgres", "mysql", "sqlite", "excel"):
        try:
            conn.execute(f"INSTALL {ext}")
            conn.execute(f"LOAD {ext}")
        except Exception as exc:
            logger.info("Optional DuckDB extension %s unavailable: %s", ext, exc)
    return conn


# The DuckDB file is opened in the FastAPI ``startup`` hook (so the worker
# process is the only one holding the file lock — important when running
# ``uvicorn --reload``, otherwise the reloader parent and the worker would
# fight for the same lock and crash on boot).
duckdb_conn: Optional[duckdb.DuckDBPyConnection] = None


def _duck() -> duckdb.DuckDBPyConnection:
    """Return the live DuckDB connection (raises if startup hasn't run yet)."""
    if duckdb_conn is None:
        raise RuntimeError("DuckDB connection is not open yet; FastAPI startup hasn't finished.")
    return duckdb_conn


# Map of datasource_id -> registration metadata (so unregister can clean up).
_datasources: Dict[str, Dict[str, Any]] = {}


# ---------------------------------------------------------------------------
# Per-session Python state
# ---------------------------------------------------------------------------

# Each session has its own ``locals()`` dict. ``duckdb_conn`` is shared.
SESSION_LOCALS: Dict[str, Dict[str, Any]] = {}
SESSION_ROLLBACK: Dict[str, Dict[str, Any]] = {}
SESSION_RUNNING: Dict[str, bool] = {}
QUEUE_DEPTH = 0


def _new_session_locals() -> Dict[str, Any]:
    # ``engine`` is kept as an alias for backwards compatibility with the
    # legacy classic analysis prompt (which uses ``pd.read_sql_query(..., con=engine)``).
    # DuckDB connection objects implement the DB-API 2.0 protocol that pandas
    # accepts.
    conn = _duck()
    return {
        "duckdb_conn": conn,
        "duck": conn,
        "engine": conn,
        "pd": pd,
        "np": np,
        "plt": plt,
    }


# ---------------------------------------------------------------------------
# Datasource registration
# ---------------------------------------------------------------------------


class RegisterDatasourceRequest(BaseModel):
    datasource_id: str
    name: str
    kind: str
    type: str
    view_names: List[str]
    config: Dict[str, Any] = {}
    sql_snippets: List[str] = []


class UnregisterDatasourceRequest(BaseModel):
    datasource_id: str
    view_names: List[str] = []


@app.post("/register-datasource")
def register_datasource(request: RegisterDatasourceRequest) -> Dict[str, Any]:
    """Apply DDL so SQL/Python code can query the new datasource."""
    try:
        for snippet in request.sql_snippets:
            _apply_snippet(snippet, request)
        _datasources[request.datasource_id] = {
            "name": request.name,
            "type": request.type,
            "view_names": list(request.view_names),
            "config": dict(request.config),
            "sql_snippets": list(request.sql_snippets),
        }
        return {"ok": True, "view_names": request.view_names}
    except Exception as exc:
        logger.exception("Failed to register datasource %s", request.datasource_id)
        raise HTTPException(status_code=400, detail=f"Registration failed: {exc}")


@app.post("/unregister-datasource")
def unregister_datasource(request: UnregisterDatasourceRequest) -> Dict[str, Any]:
    """Drop views and detach databases for a removed datasource."""
    record = _datasources.pop(request.datasource_id, None)
    view_names = list(request.view_names) if request.view_names else (record["view_names"] if record else [])

    conn = _duck()
    for view in view_names:
        try:
            conn.execute(f'DROP VIEW IF EXISTS "{view}"')
        except Exception as exc:
            logger.warning("Failed to drop view %s: %s", view, exc)

    # Best-effort detach (will silently succeed if the alias is not attached).
    if record:
        for snippet in record.get("sql_snippets", []):
            if snippet.startswith("ATTACH"):
                match = re.search(r'ATTACH\s+\'[^\']+\'\s+AS\s+"?([^"\s\(]+)"?', snippet, re.IGNORECASE)
                if match:
                    alias = match.group(1)
                    try:
                        conn.execute(f'DETACH "{alias}"')
                    except Exception as exc:
                        logger.info("Detach of %s skipped: %s", alias, exc)

    return {"ok": True, "removed": view_names}


@app.get("/datasources")
def list_datasources() -> Dict[str, Any]:
    return {"datasources": _datasources}


_PANDAS_FALLBACK_PREFIX = "-- pandas-fallback "


def _apply_snippet(snippet: str, request: RegisterDatasourceRequest) -> None:
    snippet = snippet.strip()
    if not snippet:
        return
    if snippet.startswith(_PANDAS_FALLBACK_PREFIX):
        _apply_pandas_fallback(snippet[len(_PANDAS_FALLBACK_PREFIX):], request)
        return
    if snippet.startswith("--"):
        # Plain comment / instruction we don't recognise; skip safely.
        return
    _duck().execute(snippet)


def _apply_pandas_fallback(payload: str, request: RegisterDatasourceRequest) -> None:
    """Realise a sheet/file as a DuckDB view via pandas.

    The payload is JSON, e.g. ``{"kind": "excel", "name": ..., "path": ..., "sheet": ...}``.
    """
    try:
        instruction = json.loads(payload)
    except json.JSONDecodeError as exc:
        logger.warning("Malformed pandas-fallback payload %r: %s", payload, exc)
        return

    kind = instruction.get("kind")
    name = instruction.get("name")
    path = instruction.get("path")
    sheet = instruction.get("sheet")

    if kind != "excel" or not name or not path:
        logger.warning("Unsupported pandas-fallback instruction: %s", instruction)
        return

    df = pd.read_excel(path, sheet_name=sheet) if sheet else pd.read_excel(path)
    df.columns = [str(c) for c in df.columns]
    conn = _duck()
    conn.register(f"_tmp_{name}", df)
    conn.execute(
        f'CREATE OR REPLACE VIEW "{name}" AS SELECT * FROM _tmp_{name}'
    )


# ---------------------------------------------------------------------------
# DuckDB lifecycle + bootstrap from the app
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def open_duckdb() -> None:
    """Open the DuckDB file once the worker process starts.

    Doing this in a startup hook (instead of at module import) keeps the
    file lock confined to the worker, so ``uvicorn --reload`` doesn't crash
    with ``Conflicting lock is held in ... (PID 1)``.
    """
    global duckdb_conn
    if duckdb_conn is None:
        duckdb_conn = _open_duckdb()
        logger.info("DuckDB connection opened at %s", DUCKDB_PATH)


@app.on_event("shutdown")
async def close_duckdb() -> None:
    """Release the DuckDB file lock so a reloaded worker can grab it again."""
    global duckdb_conn
    if duckdb_conn is not None:
        try:
            duckdb_conn.close()
        finally:
            duckdb_conn = None
            logger.info("DuckDB connection closed")


@app.on_event("startup")
async def bootstrap_datasources() -> None:
    """Ask the app service for the current datasource list and replay every DDL.

    Without this step a sandbox restart (uvicorn ``--reload`` triggers one
    on every code change) would leave the DuckDB catalog empty whenever
    the persistent file is fresh or pandas-fallback views (Excel without
    the ``excel`` extension) are present — those live only in memory.

    Re-applying the snippets from ``/internal/sandbox-bootstrap`` makes the
    app the single source of truth and keeps SQL/preview/agent paths in
    sync after any restart.
    """
    import httpx

    url = f"{DATASOURCE_SYNC_URL}/internal/sandbox-bootstrap"
    data: Optional[Dict[str, Any]] = None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(8):
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    data = response.json()
                    break
                except Exception as exc:
                    logger.info("Datasource bootstrap retry %s: %s", attempt + 1, exc)
                    await asyncio.sleep(2.0)
            else:
                logger.warning("Skipping datasource bootstrap; app service unreachable at %s", url)
                return
    except Exception as exc:
        logger.warning("Datasource bootstrap failed: %s", exc)
        return

    if data is None:
        return

    sources = data.get("datasources", [])
    registered = 0
    failed = 0
    for source in sources:
        try:
            request = RegisterDatasourceRequest(**source)
        except Exception as exc:
            logger.warning("Skipping malformed datasource payload from app: %s", exc)
            failed += 1
            continue

        try:
            for snippet in request.sql_snippets:
                _apply_snippet(snippet, request)
            _datasources[request.datasource_id] = {
                "name": request.name,
                "type": request.type,
                "view_names": list(request.view_names),
                "config": dict(request.config),
                "sql_snippets": list(request.sql_snippets),
            }
            registered += 1
        except Exception as exc:
            logger.warning(
                "Failed to re-register datasource %s (%s): %s",
                request.name,
                request.datasource_id,
                exc,
            )
            failed += 1

    logger.info(
        "Datasource bootstrap: %d registered, %d failed (of %d reported)",
        registered,
        failed,
        len(sources),
    )


# ---------------------------------------------------------------------------
# Status / SQL / code / variable endpoints
# ---------------------------------------------------------------------------


@app.get("/status")
def get_status() -> Dict[str, Any]:
    return {
        "que": QUEUE_DEPTH,
        "datasource_count": len(_datasources),
        "view_count": sum(len(d["view_names"]) for d in _datasources.values()),
    }


class CodeExecutionRequest(BaseModel):
    id: str
    code: str


@app.post("/code")
def execute_code(request: CodeExecutionRequest) -> Dict[str, Any]:
    """Execute Python code in the per-session sandbox."""
    global QUEUE_DEPTH
    QUEUE_DEPTH += 1

    session_id = request.id
    logger.info(
        "POST /code session=%s code_len=%d queue=%d",
        session_id,
        len(request.code),
        QUEUE_DEPTH,
    )
    logger.debug("code:\n%s", request.code)
    if session_id in SESSION_LOCALS and SESSION_LOCALS[session_id] is not None:
        localvars = SESSION_LOCALS[session_id]
    else:
        localvars = _new_session_locals()

    SESSION_ROLLBACK[session_id] = localvars.copy()

    code = request.code.replace("%@", "\\")
    # Disallow reassigning the shared DuckDB connection — keeps datasource
    # views reachable across executions.
    code = re.sub(r"^duckdb_conn\s*=.*\n?", "", code, flags=re.MULTILINE)
    code = re.sub(r"^duck\s*=.*\n?", "", code, flags=re.MULTILINE)
    code = re.sub(r"^engine\s*=.*\n?", "", code, flags=re.MULTILINE)

    SESSION_RUNNING[session_id] = True
    try:
        exec(code, localvars)
    except Exception as exc:
        QUEUE_DEPTH -= 1
        SESSION_RUNNING[session_id] = False
        logger.error("POST /code session=%s failed: %s", session_id, exc)
        return {"error": str(exc), "trace": traceback.format_exc(), "id": session_id}

    SESSION_LOCALS[session_id] = localvars
    QUEUE_DEPTH -= 1
    SESSION_RUNNING[session_id] = False
    logger.info("POST /code session=%s ok", session_id)
    return {"ok": "code executed successfully"}


class SQLExecutionRequest(BaseModel):
    id: str
    sql: str
    result_variable: str = "df_result"
    preview_limit: int = 20


@app.post("/sql")
def execute_sql(request: SQLExecutionRequest) -> Dict[str, Any]:
    """Execute a SQL statement via DuckDB and stash the result as a session variable.

    The DataFrame is materialised under ``result_variable`` (default
    ``df_result``) in the same session locals namespace ``/code`` uses, so
    follow-up Python steps can keep iterating on it.
    """
    global QUEUE_DEPTH
    QUEUE_DEPTH += 1
    session_id = request.id
    logger.info(
        "POST /sql session=%s result_var=%s sql=%r",
        session_id,
        request.result_variable,
        request.sql[:300] if request.sql else "",
    )

    if session_id not in SESSION_LOCALS or SESSION_LOCALS[session_id] is None:
        SESSION_LOCALS[session_id] = _new_session_locals()
    localvars = SESSION_LOCALS[session_id]

    try:
        df = _duck().execute(request.sql).fetchdf()
    except Exception as exc:
        QUEUE_DEPTH -= 1
        logger.error("POST /sql session=%s failed: %s", session_id, exc)
        return {
            "error": str(exc),
            "trace": traceback.format_exc(),
            "id": session_id,
            "sql": request.sql,
        }

    localvars[request.result_variable] = df
    QUEUE_DEPTH -= 1
    preview_limit = max(0, int(request.preview_limit))
    preview_df = df if preview_limit == 0 else df.head(preview_limit)
    logger.info(
        "POST /sql session=%s ok rows=%d columns=%s",
        session_id,
        len(df),
        list(df.columns),
    )
    return {
        "ok": True,
        "rows": len(df),
        "columns": list(df.columns),
        "result_variable": request.result_variable,
        "preview": preview_df.to_dict(orient="records"),
    }


class VariableRollbackRequest(BaseModel):
    id: str


@app.post("/rollback")
def rollback_variable(request: VariableRollbackRequest) -> Dict[str, Any]:
    session_id = request.id
    if session_id not in SESSION_LOCALS or session_id not in SESSION_ROLLBACK:
        return {"error": "Id not found"}

    deadline = time.time() + 10.0
    while SESSION_RUNNING.get(session_id) and time.time() < deadline:
        time.sleep(0.05)
    if SESSION_RUNNING.get(session_id):
        return {"error": "Code is still running, please try again later"}

    SESSION_LOCALS[session_id] = SESSION_ROLLBACK[session_id]
    return {"ok": "variables rolled back successfully"}


class VariableRetrievalRequest(BaseModel):
    id: str
    name: str


@app.post("/var")
def get_variable(request: VariableRetrievalRequest) -> Dict[str, Any]:
    session_id = request.id
    logger.debug("POST /var session=%s name=%s", session_id, request.name)
    if session_id not in SESSION_LOCALS:
        return {"error": "Id not found"}

    deadline = time.time() + 10.0
    while SESSION_RUNNING.get(session_id) and time.time() < deadline:
        time.sleep(0.05)
    if SESSION_RUNNING.get(session_id):
        return {"error": "Code is still running, please try again later"}

    current = SESSION_LOCALS[session_id]
    expression = request.name
    if ":." in expression:
        expression = f"f'''{{{expression}}}'''"

    try:
        result = eval(expression, {}, current)
    except Exception as exc:
        if "error" in request.name or "log" in request.name:
            return {"data": "", "type": "string"}
        return {"error": f"Error: {exc}"}

    return {"result": _to_response_payload(result)}


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _to_json(value: Any) -> Dict[str, Any]:
    if isinstance(value, pd.DataFrame):
        df_copy = value.copy()
        if not df_copy.index.equals(pd.RangeIndex(len(df_copy))):
            df_copy.insert(0, "", df_copy.index)
        return {"data": df_copy.to_json(orient="records"), "type": "table"}
    if isinstance(value, pd.Series):
        series_copy = value.copy()
        df_from_series = pd.DataFrame([series_copy])
        if not series_copy.index.equals(pd.RangeIndex(len(series_copy))):
            df_from_series.insert(0, "", series_copy.index)
        return {"data": df_from_series.to_json(orient="records"), "type": "table"}
    if isinstance(value, plt.Figure):
        buf = io.BytesIO()
        value.savefig(buf, format="jpeg")
        buf.seek(0)
        encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
        plt.close(value)
        return {"data": encoded, "type": "image"}
    return {"data": str(value), "type": "string"}


def _to_response_payload(value: Any) -> List[Dict[str, Any]]:
    if isinstance(value, list):
        return [_to_json(item) for item in value]
    if isinstance(value, dict):
        out: List[Dict[str, Any]] = []
        for key, val in value.items():
            out.append({"data": str(key), "type": "string"})
            out.append(_to_json(val))
        return out
    return [_to_json(value)]


@app.get("/health")
def health() -> Dict[str, Any]:
    return {"status": "ok", "service": "sandbox", "duckdb": True}
