"""Variable rollback and retrieval via the control layer."""
from __future__ import annotations

from typing import Any, Dict

from api.schemas import VariableRetrievalRequest, VariableRollbackRequest
from control_layer import TaskObject, get_control_layer
from execution.response import to_http_response


def rollback(request: VariableRollbackRequest) -> Dict[str, Any]:
    task = TaskObject(
        task_type="rollback",
        session_id=request.id,
    )
    result = get_control_layer().handle_task(task)
    return to_http_response(result)


def get_variable(request: VariableRetrievalRequest) -> Dict[str, Any]:
    task = TaskObject(
        task_type="get_variable",
        session_id=request.id,
        variable_name=request.name,
    )
    result = get_control_layer().handle_task(task)
    return to_http_response(result)
