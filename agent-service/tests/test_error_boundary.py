"""Tests for the worker error boundary (solution.md §9)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from langgraph.errors import GraphInterrupt  # noqa: E402

from agents.shared.error_boundary import with_error_boundary  # noqa: E402


def test_crash_becomes_error_observation():
    async def boom(state):
        raise ValueError("kaboom")

    wrapped = with_error_boundary(boom, "eda", timeout=None, max_retries=0)
    patch = asyncio.run(wrapped({"agent_steps": []}))

    assert patch["last_observation"]["status"] == "error"
    assert "kaboom" in patch["last_observation"]["error"]
    assert patch["agent_steps"] == ["eda"]


def test_timeout_becomes_error_observation():
    async def slow(state):
        await asyncio.sleep(1)

    wrapped = with_error_boundary(slow, "viz", timeout=0.01, max_retries=0)
    patch = asyncio.run(wrapped({"agent_steps": []}))

    assert patch["last_observation"]["status"] == "error"
    assert "timeout" in patch["last_observation"]["summary"].lower()


def test_graph_interrupt_propagates():
    async def needs_approval(state):
        raise GraphInterrupt("pause")

    wrapped = with_error_boundary(needs_approval, "sql", timeout=None)

    try:
        asyncio.run(wrapped({"agent_steps": []}))
        assert False, "GraphInterrupt should propagate"
    except GraphInterrupt:
        pass


def test_success_passes_through():
    async def ok(state):
        return {"current_agent": "eda", "value": 1}

    wrapped = with_error_boundary(ok, "eda")
    patch = asyncio.run(wrapped({}))
    assert patch == {"current_agent": "eda", "value": 1}
