"""Centralised environment configuration for the sandbox service."""
from __future__ import annotations

import os

DUCKDB_PATH = os.environ.get("SANDBOX_DUCKDB_PATH", ":memory:")
DATASOURCE_SYNC_URL = os.environ.get("APP_SERVICE_URL", "http://app:8000").rstrip("/")
