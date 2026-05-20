"""Tests for ReAct loop detection (solution.md §1 Fix 2)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agents.planner.plan_tracker import detect_action_loop, resolve_planner_action  # noqa: E402
from orchestration.routing.plan import build_execution_plan  # noqa: E402


def _history(actions):
    return [{"action": a} for a in actions]


def test_detect_action_loop_triggers_after_three_repeats():
    state = {"planner_history": _history(["sql", "sql", "sql"])}
    assert detect_action_loop(state, "sql") is True


def test_detect_action_loop_ignores_terminal_actions():
    state = {"planner_history": _history(["generate_result"] * 5)}
    assert detect_action_loop(state, "generate_result") is False


def test_detect_action_loop_respects_window():
    # Three sql's exist but they fall outside the 5-step window.
    state = {"planner_history": _history(["sql", "sql", "sql", "eda", "insight", "viz"])}
    assert detect_action_loop(state, "sql") is False


def test_resolve_forces_plan_step_on_loop():
    plan = build_execution_plan(["sql", "eda"], "ANALYTICAL", "sql")
    state = {
        "orchestration_mode": "EXPLORE",
        "execution_plan": plan,
        "planner_history": _history(["sql", "sql", "sql"]),
    }
    action, note = resolve_planner_action(state, "sql", last_observation={})
    assert action == "eda"
    assert "loop detected" in note


def test_resolve_forces_generate_result_when_no_pending():
    plan = build_execution_plan(["sql"], "RETRIEVAL", "sql")
    # mark the only worker step done so nothing is pending but terminal
    plan[0]["status"] = "done"
    state = {
        "orchestration_mode": "EXPLORE",
        "execution_plan": plan,
        "planner_history": _history(["sql", "sql", "sql"]),
    }
    action, note = resolve_planner_action(state, "sql", last_observation={})
    assert action == "generate_result"
