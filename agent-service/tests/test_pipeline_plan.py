"""Tests for structured execution plans and orchestration modes."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agents.planner.plan_tracker import resolve_planner_action, sync_plan_with_completed  # noqa: E402
from orchestration.routing.pipeline import normalise_pipeline  # noqa: E402
from orchestration.routing.plan import (  # noqa: E402
    build_execution_plan,
    detect_explore_intent,
    format_plan_for_prompt,
    get_next_planned_action,
    select_orchestration_mode,
    update_plan_from_reflection,
)


def test_detect_explore_intent():
    assert detect_explore_intent("Show me sales and explore the distribution") is True
    assert detect_explore_intent("Give me a deep dive on churn") is True
    assert detect_explore_intent("Show me 5 employees") is False


def test_select_orchestration_mode():
    assert select_orchestration_mode("RETRIEVAL", "list departments") == "FIXED"
    assert select_orchestration_mode("ANALYTICAL", "why are users churning") == "AUTO_PLAN"
    assert select_orchestration_mode("RETRIEVAL", "show data and explore trends") == "EXPLORE"
    assert select_orchestration_mode("RETRIEVAL", "list users", is_replan=True) == "EXPLORE"


def test_normalise_pipeline_retrieval_fixed_vs_explore():
    # The data step is collapsed to a generic "exec"; the runtime exec node
    # picks SQL vs Python (agents/executor/exec_router.py).
    fixed = normalise_pipeline(["eda", "insight"], "sql", "RETRIEVAL", "FIXED", "show 5 rows")
    assert fixed == ["exec"]

    explore = normalise_pipeline(
        ["eda", "insight"],
        "sql",
        "RETRIEVAL",
        "EXPLORE",
        "show 5 rows and explore distribution",
    )
    assert explore == ["exec", "eda", "insight"]


def test_normalise_pipeline_collapses_python_to_exec():
    # Even when the orchestrator hints python, the plan starts with exec.
    result = normalise_pipeline(["python", "eda"], "python", "ANALYTICAL", "AUTO_PLAN", "run a t-test")
    assert result[0] == "exec"
    assert "python" not in result and "sql" not in result


def test_build_execution_plan_adds_generate_result():
    plan = build_execution_plan(["exec", "eda", "insight"], "ANALYTICAL", "exec")
    actions = [step["action"] for step in plan]
    assert actions == ["exec", "eda", "insight", "generate_result"]
    assert plan[1]["rely"] == [1]
    assert plan[-1]["rely"] == [3]


def test_get_next_planned_action():
    plan = build_execution_plan(["exec", "eda"], "ANALYTICAL", "exec")
    assert get_next_planned_action(plan) == "exec"

    synced = sync_plan_with_completed(plan, ["exec"])
    assert get_next_planned_action(synced) == "eda"


def test_update_plan_from_reflection_adds_viz():
    plan = build_execution_plan(["exec", "insight"], "ANALYTICAL", "exec")
    updated = update_plan_from_reflection(plan, "User requested a chart but none was shown", "exec")
    worker_actions = [
        step["action"]
        for step in updated
        if step["action"] not in ("generate_result", "finish")
    ]
    assert "viz" in worker_actions


def test_resolve_planner_action_fixed_mode():
    plan = build_execution_plan(["exec", "eda"], "ANALYTICAL", "exec")
    state = {
        "orchestration_mode": "FIXED",
        "execution_plan": plan,
        "completed_actions": [],
    }
    action, note = resolve_planner_action(state, "insight", last_observation={})
    assert action == "exec"
    assert "FIXED" in note


def test_resolve_planner_action_auto_plan_blocks_early_finish():
    plan = build_execution_plan(["exec", "eda", "insight"], "ANALYTICAL", "exec")
    state = {
        "orchestration_mode": "AUTO_PLAN",
        "execution_plan": plan,
        "completed_actions": [],
    }
    action, _ = resolve_planner_action(state, "generate_result", last_observation={})
    assert action == "exec"


def test_format_plan_for_prompt_includes_mode():
    plan = build_execution_plan(["exec"], "RETRIEVAL", "exec")
    text = format_plan_for_prompt(plan, "FIXED")
    assert "Orchestration mode: FIXED" in text
    assert "Step 1: exec" in text
