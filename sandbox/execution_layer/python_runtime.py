"""In-process Python + DuckDB sandbox runtime for analytics workloads."""
from __future__ import annotations

import threading
import time
import traceback
from typing import Any, Dict, List, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from execution_layer.base import (
    ExecutionResult,
    ExecutionStatus,
    SandboxRuntime,
    SandboxSession,
    SessionConfig,
)
from execution_layer.limits import ExecutionTimeoutError, run_with_timeout
from execution_layer.utils import EnvironmentDetector
from execution.serialization import to_response_payload
from infrastructure.config import MAX_EXECUTION_TIME, MAX_MEMORY
from infrastructure.duckdb import get_connection
from infrastructure.logging_setup import logger
from security.utils import SecurityUtils

_QUEUE_LOCK = threading.Lock()
_QUEUE_DEPTH = 0


def increment_queue() -> int:
    global _QUEUE_DEPTH
    with _QUEUE_LOCK:
        _QUEUE_DEPTH += 1
        return _QUEUE_DEPTH


def decrement_queue() -> int:
    global _QUEUE_DEPTH
    with _QUEUE_LOCK:
        _QUEUE_DEPTH -= 1
        return _QUEUE_DEPTH


def queue_depth() -> int:
    with _QUEUE_LOCK:
        return _QUEUE_DEPTH


def _new_session_locals() -> Dict[str, Any]:
    conn = get_connection()
    return {
        "duckdb_conn": conn,
        "duck": conn,
        "engine": conn,
        "pd": pd,
        "np": np,
        "plt": plt,
    }


class PythonSandboxSession(SandboxSession):
    """Stateful in-process Python session backed by shared DuckDB."""

    def __init__(self, session_id: str, config: SessionConfig):
        super().__init__(session_id, config)
        self._lock = threading.Lock()
        self._localvars: Optional[Dict[str, Any]] = None
        self._rollback: Optional[Dict[str, Any]] = None
        self._running = False

    def start(self) -> bool:
        with self._lock:
            self._localvars = _new_session_locals()
            self._rollback = self._localvars.copy()
            self._is_active = True
        return True

    def stop(self) -> bool:
        with self._lock:
            self._localvars = None
            self._rollback = None
            self._running = False
            self._is_active = False
        return True

    def execute(self, code: str) -> ExecutionResult:
        if not self._is_active or self._localvars is None:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error="Session is not active",
                exit_code=1,
            )

        self.update_last_accessed()
        from security.code_sanitizer import sanitize_user_code

        sanitized = sanitize_user_code(code)
        timeout = self.config.timeout or MAX_EXECUTION_TIME
        warnings = SecurityUtils.validate_code(sanitized, "python")
        if warnings:
            logger.warning(
                "security warnings session=%s: %s",
                self.session_id,
                "; ".join(warnings),
            )

        with self._lock:
            self._rollback = self._localvars.copy()
            self._running = True
            localvars = self._localvars

        increment_queue()
        start = time.time()
        try:
            run_with_timeout(lambda: exec(sanitized, localvars), timeout)
        except ExecutionTimeoutError as exc:
            with self._lock:
                self._running = False
            decrement_queue()
            logger.error("execute session=%s timed out after %ss", self.session_id, timeout)
            return ExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                error=str(exc),
                output=f"Execution timed out ({timeout}s limit)",
                execution_time=time.time() - start,
                exit_code=124,
                payload={"id": self.session_id, "timeout": timeout},
            )
        except Exception as exc:
            with self._lock:
                self._running = False
            decrement_queue()
            logger.error("execute session=%s failed: %s", self.session_id, exc)
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error=str(exc),
                output=traceback.format_exc(),
                execution_time=time.time() - start,
                exit_code=1,
                payload={"trace": traceback.format_exc(), "id": self.session_id},
            )
        finally:
            with self._lock:
                self._running = False

        decrement_queue()
        elapsed = time.time() - start
        logger.info("execute session=%s ok (%.3fs)", self.session_id, elapsed)
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            output="code executed successfully",
            execution_time=elapsed,
            exit_code=0,
            payload={"ok": "code executed successfully", "id": self.session_id},
        )

    def execute_sql(
        self,
        sql: str,
        result_variable: str = "df_result",
        preview_limit: int = 20,
    ) -> ExecutionResult:
        if not self._is_active or self._localvars is None:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error="Session is not active",
                exit_code=1,
            )

        self.update_last_accessed()
        timeout = self.config.timeout or MAX_EXECUTION_TIME
        increment_queue()
        start = time.time()
        try:
            df = run_with_timeout(
                lambda: get_connection().execute(sql).fetchdf(),
                timeout,
            )
        except ExecutionTimeoutError as exc:
            decrement_queue()
            logger.error("execute_sql session=%s timed out: %s", self.session_id, exc)
            return ExecutionResult(
                status=ExecutionStatus.TIMEOUT,
                error=str(exc),
                output=f"SQL execution timed out ({timeout}s limit)",
                execution_time=time.time() - start,
                exit_code=124,
                payload={"id": self.session_id, "sql": sql, "timeout": timeout},
            )
        except Exception as exc:
            decrement_queue()
            logger.error("execute_sql session=%s failed: %s", self.session_id, exc)
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error=str(exc),
                output=traceback.format_exc(),
                execution_time=time.time() - start,
                exit_code=1,
                payload={
                    "trace": traceback.format_exc(),
                    "id": self.session_id,
                    "sql": sql,
                },
            )

        with self._lock:
            self._localvars[result_variable] = df

        decrement_queue()
        preview_df = df if preview_limit <= 0 else df.head(preview_limit)
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            execution_time=time.time() - start,
            exit_code=0,
            payload={
                "ok": True,
                "rows": len(df),
                "columns": list(df.columns),
                "result_variable": result_variable,
                "preview": preview_df.to_dict(orient="records"),
                "id": self.session_id,
            },
        )

    def rollback_variables(self) -> ExecutionResult:
        if not self._is_active or self._localvars is None or self._rollback is None:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error="Id not found",
                exit_code=1,
            )
        if not self._wait_for_idle():
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error="Code is still running, please try again later",
                exit_code=1,
            )
        with self._lock:
            self._localvars.clear()
            self._localvars.update(self._rollback)
        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            output="variables rolled back successfully",
            payload={"ok": "variables rolled back successfully"},
        )

    def get_variable(self, name: str) -> ExecutionResult:
        if not self._is_active or self._localvars is None:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error="Id not found",
                exit_code=1,
            )
        if not self._wait_for_idle():
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error="Code is still running, please try again later",
                exit_code=1,
            )

        expression = name
        if ":." in expression:
            expression = f"f'''{{{expression}}}'''"

        with self._lock:
            localvars = self._localvars
            try:
                result = eval(expression, {}, localvars)
            except Exception as exc:
                if "error" in name or "log" in name:
                    return ExecutionResult(
                        status=ExecutionStatus.SUCCESS,
                        payload={"data": "", "type": "string"},
                    )
                return ExecutionResult(
                    status=ExecutionStatus.ERROR,
                    error=f"Error: {exc}",
                    exit_code=1,
                )

        return ExecutionResult(
            status=ExecutionStatus.SUCCESS,
            payload={"result": to_response_payload(result)},
        )

    def _wait_for_idle(self, deadline_seconds: float = 10.0) -> bool:
        deadline = time.time() + deadline_seconds
        while self._running and time.time() < deadline:
            time.sleep(0.05)
        return not self._running

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "status": "running" if self._is_active else "stopped",
                "session_id": self.session_id,
                "created_at": self.created_at,
                "last_accessed": self.last_accessed,
                "is_running": self._running,
                "has_locals": self._localvars is not None,
            }


def _default_session_config() -> SessionConfig:
    return SessionConfig(timeout=MAX_EXECUTION_TIME, max_memory=MAX_MEMORY)


class PythonRuntime(SandboxRuntime):
    """In-process Python runtime (default for analytics sandbox)."""

    def __init__(self, runtime_id: str = "python"):
        super().__init__(runtime_id)

    def create_session(self, session_id: str, config: SessionConfig) -> PythonSandboxSession:
        if session_id in self.sessions:
            return self.sessions[session_id]  # type: ignore[return-value]

        session = PythonSandboxSession(session_id, config)
        if session.start():
            self.sessions[session_id] = session
            return session
        raise RuntimeError(f"Failed to start session {session_id}")

    def get_or_create_session(
        self,
        session_id: str,
        config: Optional[SessionConfig] = None,
    ) -> PythonSandboxSession:
        existing = self.sessions.get(session_id)
        if existing is not None:
            return existing  # type: ignore[return-value]
        return self.create_session(session_id, config or _default_session_config())

    def destroy_session(self, session_id: str) -> bool:
        session = self.sessions.pop(session_id, None)
        if session is None:
            return False
        return session.stop()

    def list_sessions(self) -> List[str]:
        return list(self.sessions.keys())

    def get_session(self, session_id: str) -> Optional[PythonSandboxSession]:
        return self.sessions.get(session_id)  # type: ignore[return-value]

    def cleanup_expired_sessions(self, max_idle_time: int = 3600) -> int:
        current = time.time()
        expired = [
            sid
            for sid, session in self.sessions.items()
            if current - session.last_accessed > max_idle_time
        ]
        cleaned = 0
        for sid in expired:
            if self.destroy_session(sid):
                cleaned += 1
        return cleaned

    def health_check(self) -> Dict[str, Any]:
        try:
            return {
                "status": "healthy",
                "runtime": self.runtime_id,
                "system_info": EnvironmentDetector.get_system_info(),
                "active_sessions": len(self.sessions),
                "queue_depth": queue_depth(),
                "supported_languages": ["python"],
            }
        except Exception as exc:
            return {"status": "unhealthy", "error": str(exc)}

    def supports_language(self, language: str) -> bool:
        return language.lower() in {"python", "sql"}
