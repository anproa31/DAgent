"""Centralised environment configuration for the sandbox service."""
from __future__ import annotations

import os

DUCKDB_PATH = os.environ.get("SANDBOX_DUCKDB_PATH", ":memory:")
DATASOURCE_SYNC_URL = os.environ.get("APP_SERVICE_URL", "http://app:8000").rstrip("/")

# Resource limits (aligned with dbgpt-sandbox defaults)
MAX_MEMORY = int(os.environ.get("SANDBOX_MAX_MEMORY", str(256 * 1024 * 1024)))
MAX_CPU_PERCENT = float(os.environ.get("SANDBOX_MAX_CPU_PERCENT", "50.0"))
MAX_EXECUTION_TIME = int(os.environ.get("SANDBOX_MAX_EXECUTION_TIME", "30"))
MAX_FILE_SIZE = int(os.environ.get("SANDBOX_MAX_FILE_SIZE", str(10 * 1024 * 1024)))
MAX_PROCESSES = int(os.environ.get("SANDBOX_MAX_PROCESSES", "10"))

# python = in-process analytics runtime (default)
# docker/podman/local reserved for future container runtimes
SANDBOX_RUNTIME = os.environ.get("SANDBOX_RUNTIME", "python")
SESSION_IDLE_SECONDS = int(os.environ.get("SANDBOX_SESSION_IDLE_SECONDS", "3600"))
SESSION_CLEANUP_INTERVAL = int(os.environ.get("SANDBOX_SESSION_CLEANUP_INTERVAL", "300"))
