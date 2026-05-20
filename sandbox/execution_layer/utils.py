"""Resource, path, and environment helpers (adapted from dbgpt-sandbox)."""
from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass
from typing import Any, Dict

import psutil

from infrastructure.config import (
    MAX_CPU_PERCENT,
    MAX_EXECUTION_TIME,
    MAX_FILE_SIZE,
    MAX_MEMORY,
    MAX_PROCESSES,
)


@dataclass
class ResourceLimits:
    max_memory: int = MAX_MEMORY
    max_cpu_percent: float = MAX_CPU_PERCENT
    max_execution_time: int = MAX_EXECUTION_TIME
    max_file_size: int = MAX_FILE_SIZE
    max_processes: int = MAX_PROCESSES


class EnvironmentDetector:
    @staticmethod
    def is_docker_available() -> bool:
        return shutil.which("docker") is not None

    @staticmethod
    def is_podman_available() -> bool:
        return shutil.which("podman") is not None

    @staticmethod
    def is_nerdctl_available() -> bool:
        return shutil.which("nerdctl") is not None

    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        return {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "cpu_count": psutil.cpu_count(),
            "memory_total": psutil.virtual_memory().total,
            "memory_available": psutil.virtual_memory().available,
            "disk_usage": psutil.disk_usage("/").percent
            if os.name != "nt"
            else psutil.disk_usage("C:").percent,
        }
