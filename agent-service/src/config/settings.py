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


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


# --- Agent loop / reliability tuning (solution.md P0 + P1) ---

# ReAct loop: force the planner to wrap up once it has spent this many steps
# without reaching generate_result (solution.md §1 Fix 4).
FORCED_EXIT_THRESHOLD = _int_env("FORCED_EXIT_THRESHOLD", 10)

# Loop detection sliding window (solution.md §1 Fix 2): if the same action
# repeats LOOP_DETECTION_REPEAT times within the last LOOP_DETECTION_WINDOW
# planner steps, force progress along the plan.
LOOP_DETECTION_WINDOW = _int_env("LOOP_DETECTION_WINDOW", 5)
LOOP_DETECTION_REPEAT = _int_env("LOOP_DETECTION_REPEAT", 3)

# Reflection loop bounds (solution.md §2).
MAX_REFLECTION_PASSES = _int_env("MAX_REFLECTION_PASSES", 2)
REFLECTION_QUALITY_THRESHOLD = _float_env("REFLECTION_QUALITY_THRESHOLD", 0.75)
MAX_REFLECTION_RERUNS = _int_env("MAX_REFLECTION_RERUNS", 1)

# Worker error boundary (solution.md §9).
WORKER_TIMEOUT_SECONDS = _int_env("WORKER_TIMEOUT_SECONDS", 120)
WORKER_MAX_RETRIES = _int_env("WORKER_MAX_RETRIES", 1)

# Human-in-the-loop approval TTL (solution.md §6).
HITL_TIMEOUT_SECONDS = _int_env("HITL_TIMEOUT_SECONDS", 1800)

# Planner context window budget (solution.md §8): how many recent observations
# the planner reads in full-summary form before older ones are compressed.
PLANNER_RECENT_OBSERVATIONS = _int_env("PLANNER_RECENT_OBSERVATIONS", 3)
