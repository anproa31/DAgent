"""Tests for the summarised planner context (solution.md §1 Fix 1/3, §8)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agents.planner.context_builder import (  # noqa: E402
    build_planner_context,
    collect_observations,
    format_failed_attempts,
)


def _obs(agent, status, summary, **artifacts):
    return {
        "agent": agent,
        "status": status,
        "summary": summary,
        "artifacts": artifacts,
        "error": artifacts.get("error"),
        "next_hint": artifacts.get("next_hint"),
    }


def test_collect_observations_appends_latest():
    state = {
        "planner_history": [
            {"action": "sql", "observation": _obs("code_executor", "success", "10 rows")},
        ],
        "last_observation": _obs("eda", "success", "EDA done"),
    }
    obs = collect_observations(state)
    assert [o["agent"] for o in obs] == ["code_executor", "eda"]


def test_context_excludes_raw_data():
    big = "x" * 5000
    state = {
        "planner_history": [],
        "last_observation": _obs("code_executor", "success", "200 rows", rows=200, raw=big),
    }
    ctx = build_planner_context(state)
    assert big not in ctx
    assert "rows=200" in ctx


def test_failed_attempts_block():
    observations = [
        _obs("sql", "error", "syntax error", error="column total_amt not found"),
        _obs("eda", "success", "ok"),
    ]
    block = format_failed_attempts(observations)
    assert "Failed attempts" in block
    assert "total_amt" in block


def test_first_step_context():
    assert "first step" in build_planner_context({}).lower()
