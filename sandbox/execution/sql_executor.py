"""Execute SQL via DuckDB through the control layer."""
from __future__ import annotations

from typing import Any, Dict

from api.schemas import SQLExecutionRequest
from control_layer import TaskObject, get_control_layer
from execution.response import to_http_response


def execute(request: SQLExecutionRequest) -> Dict[str, Any]:
    task = TaskObject(
        task_type="execute_sql",
        session_id=request.id,
        sql=request.sql,
        result_variable=request.result_variable,
        preview_limit=request.preview_limit,
    )
    result = get_control_layer().handle_task(task)
    return to_http_response(result)
