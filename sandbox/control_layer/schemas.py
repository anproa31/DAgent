"""Control layer task schemas (adapted from dbgpt-sandbox user_layer)."""
from __future__ import annotations

from typing import Any, Dict, Optional

TASK_TYPES = [
    "connect",
    "execute_code",
    "execute_sql",
    "rollback",
    "get_variable",
    "disconnect",
    "status",
]


class TaskObject:
    def __init__(
        self,
        task_type: str,
        session_id: str,
        *,
        code: Optional[str] = None,
        sql: Optional[str] = None,
        result_variable: str = "df_result",
        preview_limit: int = 20,
        variable_name: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        if task_type not in TASK_TYPES:
            raise ValueError(f"Invalid task_type: {task_type}")
        self.task_type = task_type
        self.session_id = session_id
        self.code = code
        self.sql = sql
        self.result_variable = result_variable
        self.preview_limit = preview_limit
        self.variable_name = variable_name
        self.config = config or {}
