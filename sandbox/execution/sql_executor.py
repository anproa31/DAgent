"""Execute SQL via DuckDB and stash results in session locals."""
from __future__ import annotations

import traceback
from typing import Any, Dict

from api.schemas import SQLExecutionRequest
from execution import session
from infrastructure.duckdb import get_connection
from infrastructure.logging_setup import logger


def execute(request: SQLExecutionRequest) -> Dict[str, Any]:
    session_id = request.id
    session.increment_queue()

    logger.info(
        "POST /sql session=%s result_var=%s sql=%r",
        session_id,
        request.result_variable,
        request.sql[:300] if request.sql else "",
    )

    localvars = session.get_or_create_locals(session_id)

    try:
        df = get_connection().execute(request.sql).fetchdf()
    except Exception as exc:
        session.decrement_queue()
        logger.error("POST /sql session=%s failed: %s", session_id, exc)
        return {
            "error": str(exc),
            "trace": traceback.format_exc(),
            "id": session_id,
            "sql": request.sql,
        }

    localvars[request.result_variable] = df
    session.decrement_queue()
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
