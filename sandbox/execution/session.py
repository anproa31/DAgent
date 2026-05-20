"""Per-session Python locals and execution coordination state."""
from __future__ import annotations

from typing import Any, Dict

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from infrastructure.duckdb import get_connection

SESSION_LOCALS: Dict[str, Dict[str, Any]] = {}
SESSION_ROLLBACK: Dict[str, Dict[str, Any]] = {}
SESSION_RUNNING: Dict[str, bool] = {}
QUEUE_DEPTH = 0


def new_session_locals() -> Dict[str, Any]:
    conn = get_connection()
    return {
        "duckdb_conn": conn,
        "duck": conn,
        "engine": conn,
        "pd": pd,
        "np": np,
        "plt": plt,
    }


def get_or_create_locals(session_id: str) -> Dict[str, Any]:
    if session_id in SESSION_LOCALS and SESSION_LOCALS[session_id] is not None:
        return SESSION_LOCALS[session_id]
    localvars = new_session_locals()
    SESSION_LOCALS[session_id] = localvars
    return localvars


def increment_queue() -> int:
    global QUEUE_DEPTH
    QUEUE_DEPTH += 1
    return QUEUE_DEPTH


def decrement_queue() -> int:
    global QUEUE_DEPTH
    QUEUE_DEPTH -= 1
    return QUEUE_DEPTH


def queue_depth() -> int:
    return QUEUE_DEPTH
