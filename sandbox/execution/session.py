"""Per-session Python locals and execution coordination state.

Backward-compatible facade over execution_layer.python_runtime.
"""
from __future__ import annotations

from typing import Any, Dict

from execution_layer.python_runtime import (
    decrement_queue as _decrement_queue,
    increment_queue as _increment_queue,
    queue_depth as _queue_depth,
)

# Legacy module-level dicts kept for compatibility with older imports.
SESSION_LOCALS: Dict[str, Dict[str, Any]] = {}
SESSION_ROLLBACK: Dict[str, Dict[str, Any]] = {}
SESSION_RUNNING: Dict[str, bool] = {}


def new_session_locals() -> Dict[str, Any]:
    raise RuntimeError("Use control_layer.get_control_layer() instead of new_session_locals()")


def get_or_create_locals(session_id: str) -> Dict[str, Any]:
    raise RuntimeError("Use control_layer.get_control_layer() instead of get_or_create_locals()")


def increment_queue() -> int:
    return _increment_queue()


def decrement_queue() -> int:
    return _decrement_queue()


def queue_depth() -> int:
    return _queue_depth()
