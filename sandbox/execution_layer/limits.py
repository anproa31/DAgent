"""Execution time limits for in-process sandbox runs."""
from __future__ import annotations

import concurrent.futures
from typing import Callable, TypeVar

T = TypeVar("T")


class ExecutionTimeoutError(TimeoutError):
    """Raised when sandbox execution exceeds the configured timeout."""


def run_with_timeout(func: Callable[[], T], timeout_seconds: float) -> T:
    """Run *func* in a worker thread and raise if it exceeds *timeout_seconds*."""
    if timeout_seconds <= 0:
        return func()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(func)
        try:
            return future.result(timeout=timeout_seconds)
        except concurrent.futures.TimeoutError as exc:
            raise ExecutionTimeoutError(
                f"Execution timed out after {timeout_seconds}s"
            ) from exc
