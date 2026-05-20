"""Optional dbgpt-sandbox-style session management routes."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from control_layer import TaskObject, get_control_layer
from execution.response import to_http_response

router = APIRouter(prefix="/api", tags=["sandbox-sessions"])


class ConnectRequest(BaseModel):
    user_id: str
    task_id: str
    image_type: str = "python"


class DisconnectRequest(BaseModel):
    user_id: str
    task_id: str


class ExecuteRequest(BaseModel):
    session_id: str
    code_type: str = "python"
    code_content: str


class StatusRequest(BaseModel):
    session_id: str


def _session_id(user_id: str, task_id: str) -> str:
    return f"{user_id}_{task_id}"


@router.post("/connect")
def connect(req: ConnectRequest) -> Dict[str, Any]:
    task = TaskObject(
        task_type="connect",
        session_id=_session_id(req.user_id, req.task_id),
        config={"language": req.image_type},
    )
    return to_http_response(get_control_layer().handle_task(task))


@router.post("/disconnect")
def disconnect(req: DisconnectRequest) -> Dict[str, Any]:
    task = TaskObject(
        task_type="disconnect",
        session_id=_session_id(req.user_id, req.task_id),
    )
    return to_http_response(get_control_layer().handle_task(task))


@router.post("/execute")
def execute(req: ExecuteRequest) -> Dict[str, Any]:
    task = TaskObject(
        task_type="execute_code",
        session_id=req.session_id,
        code=req.code_content,
        config={"language": req.code_type},
    )
    return to_http_response(get_control_layer().handle_task(task))


@router.post("/status")
def status(req: StatusRequest) -> Dict[str, Any]:
    task = TaskObject(
        task_type="status",
        session_id=req.session_id,
    )
    return to_http_response(get_control_layer().handle_task(task))
