"""Execute Python code in per-session sandbox locals."""
from __future__ import annotations

import traceback
from typing import Any, Dict

from api.schemas import CodeExecutionRequest
from execution import session
from infrastructure.logging_setup import logger
from security.code_sanitizer import sanitize_user_code


def execute(request: CodeExecutionRequest) -> Dict[str, Any]:
    session_id = request.id
    queue = session.increment_queue()

    logger.info(
        "POST /code session=%s code_len=%d queue=%d",
        session_id,
        len(request.code),
        queue,
    )
    logger.debug("code:\n%s", request.code)

    if session_id in session.SESSION_LOCALS and session.SESSION_LOCALS[session_id] is not None:
        localvars = session.SESSION_LOCALS[session_id]
    else:
        localvars = session.new_session_locals()

    session.SESSION_ROLLBACK[session_id] = localvars.copy()
    code = sanitize_user_code(request.code)

    session.SESSION_RUNNING[session_id] = True
    try:
        exec(code, localvars)
    except Exception as exc:
        session.decrement_queue()
        session.SESSION_RUNNING[session_id] = False
        logger.error("POST /code session=%s failed: %s", session_id, exc)
        return {"error": str(exc), "trace": traceback.format_exc(), "id": session_id}

    session.SESSION_LOCALS[session_id] = localvars
    session.decrement_queue()
    session.SESSION_RUNNING[session_id] = False
    logger.info("POST /code session=%s ok", session_id)
    return {"ok": "code executed successfully"}
