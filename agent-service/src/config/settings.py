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

# --- Memory system (memory.md) ---
# Vector store + working-memory cache.
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333").rstrip("/")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")

# Embedding endpoint. Fallback only — the frontend Settings UI sends per-request overrides.
# nomic-embed-text emits 768-dim vectors, so Qdrant collections must use size=768.
EMBEDDING_BASE_URL = os.getenv("EMBEDDING_BASE_URL", "http://localhost:11434/v1")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

# LLM used by Mem0 fact-extraction + episodic consolidation (OpenAI-compatible endpoint).
MEMORY_LLM_MODEL = os.getenv("MEMORY_LLM_MODEL", "gpt-4o-mini")

# Memory scoping key (no auth model yet); KB/skills are global per deployment.
MEMORY_USER_ID = os.getenv("MEMORY_USER_ID", "default")


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

# --- Memory system numeric tuning (memory.md) ---
EMBEDDING_DIMS = _int_env("EMBEDDING_DIMS", 768)
MAX_UPLOAD_SIZE_MB = _int_env("MAX_UPLOAD_SIZE_MB", 50)
CHUNK_SIZE = _int_env("CHUNK_SIZE", 500)
CHUNK_OVERLAP = _int_env("CHUNK_OVERLAP", 50)
WORKING_MEMORY_TTL_SECONDS = _int_env("WORKING_MEMORY_TTL_SECONDS", 7200)
