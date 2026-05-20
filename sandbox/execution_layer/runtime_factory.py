"""Runtime selection (adapted from dbgpt-sandbox)."""
from __future__ import annotations

from execution_layer.base import SandboxRuntime
from execution_layer.python_runtime import PythonRuntime
from execution_layer.utils import EnvironmentDetector
from infrastructure.config import SANDBOX_RUNTIME


class RuntimeFactory:
    """Select the sandbox runtime implementation."""

    @staticmethod
    def create(runtime_preference: str | None = None) -> SandboxRuntime:
        preference = (runtime_preference or SANDBOX_RUNTIME or "python").lower()

        if preference in {"python", "local", "inprocess"}:
            return PythonRuntime()

        if preference == "docker" and EnvironmentDetector.is_docker_available():
            # Container runtimes can be added later; fall back to in-process Python.
            pass

        return PythonRuntime()
