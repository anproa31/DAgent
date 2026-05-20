"""Execute Python code via the control layer."""
from __future__ import annotations

from typing import Any, Dict

from api.schemas import CodeExecutionRequest
from control_layer import TaskObject, get_control_layer
from execution.response import to_http_response


def execute(request: CodeExecutionRequest) -> Dict[str, Any]:
    task = TaskObject(
        task_type="execute_code",
        session_id=request.id,
        code=request.code,
    )
    result = get_control_layer().handle_task(task)
    return to_http_response(result)
