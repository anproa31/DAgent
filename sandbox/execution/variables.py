"""Variable rollback and retrieval from session locals."""
from __future__ import annotations

import time
from typing import Any, Dict

from api.schemas import VariableRetrievalRequest, VariableRollbackRequest
from execution import session
from execution.serialization import to_response_payload
from infrastructure.logging_setup import logger


def _wait_for_session_idle(session_id: str, deadline_seconds: float = 10.0) -> bool:
    deadline = time.time() + deadline_seconds
    while session.SESSION_RUNNING.get(session_id) and time.time() < deadline:
        time.sleep(0.05)
    return not session.SESSION_RUNNING.get(session_id)


def rollback(request: VariableRollbackRequest) -> Dict[str, Any]:
    session_id = request.id
    if session_id not in session.SESSION_LOCALS or session_id not in session.SESSION_ROLLBACK:
        return {"error": "Id not found"}

    if not _wait_for_session_idle(session_id):
        return {"error": "Code is still running, please try again later"}

    session.SESSION_LOCALS[session_id] = session.SESSION_ROLLBACK[session_id]
    return {"ok": "variables rolled back successfully"}


def get_variable(request: VariableRetrievalRequest) -> Dict[str, Any]:
    session_id = request.id
    logger.debug("POST /var session=%s name=%s", session_id, request.name)
    if session_id not in session.SESSION_LOCALS:
        return {"error": "Id not found"}

    if not _wait_for_session_idle(session_id):
        return {"error": "Code is still running, please try again later"}

    current = session.SESSION_LOCALS[session_id]
    expression = request.name
    if ":." in expression:
        expression = f"f'''{{{expression}}}'''"

    try:
        result = eval(expression, {}, current)
    except Exception as exc:
        if "error" in request.name or "log" in request.name:
            return {"data": "", "type": "string"}
        return {"error": f"Error: {exc}"}

    return {"result": to_response_payload(result)}
