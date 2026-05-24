"""Working memory (memory.md Phase 1): Redis-backed in-session state.

Holds the active dataset schema, recent tool outputs, and the conversation log for one
session. Auto-expires after ``WORKING_MEMORY_TTL_SECONDS`` (default 2h). ``clear()`` returns a
snapshot for consolidation and deletes the key.

Stored as a single JSON document per session for simple atomic read/replace; the TTL is
refreshed on every write.
"""

from __future__ import annotations

import json
from typing import Any

import redis

from config.settings import REDIS_URL, WORKING_MEMORY_TTL_SECONDS
from utils.agent_logger import get_logger

logger = get_logger("memory.working")

_MAX_TOOL_OUTPUTS = 20
_MAX_MESSAGES = 50


def _empty_state() -> dict[str, Any]:
    return {"dataset_schema": None, "tool_outputs": [], "messages": []}


class WorkingMemory:
    def __init__(self, session_id: str, redis_url: str | None = None):
        self.session_id = session_id
        self.key = f"working:{session_id}"
        self._client = redis.Redis.from_url(redis_url or REDIS_URL, decode_responses=True)

    # ── internal ───────────────────────────────────────────────────────────
    def _read(self) -> dict[str, Any]:
        raw = self._client.get(self.key)
        if not raw:
            return _empty_state()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return _empty_state()

    def _write(self, state: dict[str, Any]) -> None:
        self._client.set(self.key, json.dumps(state), ex=WORKING_MEMORY_TTL_SECONDS)

    # ── writes ───────────────────────────────────────────────────────────────
    def set_dataset_schema(self, schema: Any) -> None:
        state = self._read()
        state["dataset_schema"] = schema
        self._write(state)

    def add_message(self, role: str, content: str) -> None:
        state = self._read()
        state["messages"].append({"role": role, "content": content})
        state["messages"] = state["messages"][-_MAX_MESSAGES:]
        self._write(state)

    def append_tool_output(self, output: Any) -> None:
        state = self._read()
        state["tool_outputs"].append(output)
        state["tool_outputs"] = state["tool_outputs"][-_MAX_TOOL_OUTPUTS:]
        self._write(state)

    # ── reads ────────────────────────────────────────────────────────────────
    def get_context_snapshot(self) -> dict[str, Any]:
        return self._read()

    def clear(self) -> dict[str, Any]:
        """Return the final snapshot (for consolidation) and delete the key."""
        snapshot = self._read()
        try:
            self._client.delete(self.key)
        except redis.RedisError as e:  # pragma: no cover - best effort
            logger.warning("failed to clear working memory %s: %s", self.session_id, e)
        return snapshot
