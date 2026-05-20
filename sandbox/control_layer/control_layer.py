"""Control layer: task lifecycle and execution dispatch."""
from __future__ import annotations

import threading
from typing import Any, Dict

from control_layer.schemas import TASK_TYPES, TaskObject
from execution_layer.base import ExecutionResult, ExecutionStatus, SessionConfig
from execution_layer.python_runtime import PythonRuntime, queue_depth
from execution_layer.runtime_factory import RuntimeFactory
from infrastructure.config import MAX_EXECUTION_TIME, MAX_MEMORY
from infrastructure.logging_setup import logger


class ControlLayer:
    """Dispatch sandbox tasks to the active runtime."""

    def __init__(self) -> None:
        self.runtime = RuntimeFactory.create()
        self._locks: Dict[str, threading.Lock] = {}

    def handle_task(self, task: TaskObject) -> ExecutionResult:
        if task.task_type not in TASK_TYPES:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error=f"Unknown task type: {task.task_type}",
                exit_code=1,
            )

        handler_map = {
            "connect": self._handle_connect,
            "execute_code": self._handle_execute_code,
            "execute_sql": self._handle_execute_sql,
            "rollback": self._handle_rollback,
            "get_variable": self._handle_get_variable,
            "disconnect": self._handle_disconnect,
            "status": self._handle_status,
        }
        handler = handler_map[task.task_type]
        lock = self._locks.setdefault(task.session_id, threading.Lock())
        with lock:
            return handler(task)

    def _get_python_runtime(self) -> PythonRuntime:
        if not isinstance(self.runtime, PythonRuntime):
            raise RuntimeError("Current runtime does not support analytics execution")
        return self.runtime

    def _handle_connect(self, task: TaskObject) -> ExecutionResult:
        runtime = self._get_python_runtime()
        config = SessionConfig(
            language=task.config.get("language", "python"),
            timeout=task.config.get("timeout", MAX_EXECUTION_TIME),
            max_memory=task.config.get("max_memory", MAX_MEMORY),
            max_cpus=task.config.get("max_cpus", 1),
            network_disabled=task.config.get("network_disabled", False),
            environment_vars=task.config.get("env", {}),
        )
        try:
            session = runtime.create_session(task.session_id, config)
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                output=f"session {session.session_id} connected",
                payload={"session_id": session.session_id, "status": "connected"},
            )
        except Exception as exc:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error=f"Connect failed: {exc}",
                exit_code=1,
            )

    def _handle_execute_code(self, task: TaskObject) -> ExecutionResult:
        runtime = self._get_python_runtime()
        session = runtime.get_or_create_session(task.session_id)
        logger.info(
            "execute_code session=%s code_len=%d queue=%d",
            task.session_id,
            len(task.code or ""),
            queue_depth(),
        )
        return session.execute(task.code or "")

    def _handle_execute_sql(self, task: TaskObject) -> ExecutionResult:
        runtime = self._get_python_runtime()
        session = runtime.get_or_create_session(task.session_id)
        logger.info(
            "execute_sql session=%s var=%s sql=%r",
            task.session_id,
            task.result_variable,
            (task.sql or "")[:300],
        )
        return session.execute_sql(
            task.sql or "",
            result_variable=task.result_variable,
            preview_limit=task.preview_limit,
        )

    def _handle_rollback(self, task: TaskObject) -> ExecutionResult:
        runtime = self._get_python_runtime()
        session = runtime.get_session(task.session_id)
        if session is None:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error="Id not found",
                exit_code=1,
            )
        return session.rollback_variables()

    def _handle_get_variable(self, task: TaskObject) -> ExecutionResult:
        runtime = self._get_python_runtime()
        session = runtime.get_session(task.session_id)
        if session is None:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error="Id not found",
                exit_code=1,
            )
        return session.get_variable(task.variable_name or "")

    def _handle_disconnect(self, task: TaskObject) -> ExecutionResult:
        success = self.runtime.destroy_session(task.session_id)
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS if success else ExecutionStatus.ERROR,
            output="session destroyed" if success else "session not found",
            payload={"ok": success},
        )

    def _handle_status(self, task: TaskObject) -> ExecutionResult:
        runtime = self._get_python_runtime()
        session = runtime.get_session(task.session_id)
        if session is None:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error="Session not found",
                exit_code=1,
            )
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            payload=session.get_status(),
        )

    def runtime_health(self) -> Dict[str, Any]:
        return self.runtime.health_check()

    def list_sessions(self) -> list[str]:
        return self.runtime.list_sessions()

    def queue_depth(self) -> int:
        return queue_depth()


_control_layer: ControlLayer | None = None


def get_control_layer() -> ControlLayer:
    global _control_layer
    if _control_layer is None:
        _control_layer = ControlLayer()
    return _control_layer
