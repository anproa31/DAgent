"""Centralized environment configuration."""

from __future__ import annotations

import os
from pathlib import Path

SERVICE_ROOT = Path(__file__).resolve().parents[2]

APP_SERVICE_URL = os.getenv("APP_SERVICE_URL", "http://app:8000").rstrip("/")
CONTEXT_ENGINE_URL = os.getenv("CONTEXT_ENGINE_URL", "http://context-engine:8002").rstrip("/")
CODE_RUNNER_URL = os.getenv("CODE_RUNNER_URL", "http://sandbox:8001/").rstrip("/")

DEFAULT_DB_PATH = SERVICE_ROOT / "data" / "agent.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{DEFAULT_DB_PATH}")
