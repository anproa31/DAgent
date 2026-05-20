"""Planner-side plan tracking and action resolution."""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List

from agents.shared.state import AgentState
from config.settings import LOOP_DETECTION_REPEAT, LOOP_DETECTION_WINDOW
from orchestration.routing.plan import (
    OrchestrationMode,
    PlanStep,
    get_next_planned_action,
    mark_plan_step_status,
)

# Map worker observation agent names back to planner actions.
_OBSERVATION_TO_ACTION = {
    "sql": "sql",
    "code_executor": "sql",
    "python": "python",
    "web_discover": "discover_data",
    "eda": "eda",
    "insight": "insight",
    "viz": "viz",
    "final_report": "generate_result",
}


def observation_to_action(observation: Dict[str, Any]) -> str | None:
    agent = observation.get("agent", "")
    return _OBSERVATION_TO_ACTION.get(agent)


def update_completed_actions(state: AgentState) -> List[str]:
    """Append the action implied by the latest successful observation."""
    observation = state.get("last_observation") or {}
    if not observation:
        return list(state.get("completed_actions") or [])

    action = observation_to_action(observation)
    if not action:
        return list(state.get("completed_actions") or [])

    completed = list(state.get("completed_actions") or [])
    status = observation.get("status", "")
    if status == "success" and action not in completed:
        completed.append(action)
    return completed


def sync_plan_with_completed(
    plan: List[PlanStep],
    completed_actions: List[str],
) -> List[PlanStep]:
    """Mark plan steps done when their actions appear in completed_actions."""
    updated = [dict(step) for step in plan]
    action_counts: Dict[str, int] = {}
    for action in completed_actions:
        action_counts[action] = action_counts.get(action, 0) + 1

    for action, needed in action_counts.items():
        marked = 0
        for step in updated:
            if step.get("action") != action:
                continue
            if step.get("status") in ("done", "skipped"):
                continue
            if marked < needed:
                step["status"] = "done"
                marked += 1
    return updated  # type: ignore[return-value]


def record_action_failure(plan: List[PlanStep], action: str) -> List[PlanStep]:
    return mark_plan_step_status(plan, action, "failed")


def detect_action_loop(state: AgentState, proposed_action: str) -> bool:
    """True when ``proposed_action`` is stuck repeating (solution.md §1 Fix 2).

    Sliding window over recent planner steps: if the same action already ran
    ``LOOP_DETECTION_REPEAT`` times within the last ``LOOP_DETECTION_WINDOW``
    steps, the planner is looping and must be forced to make progress.
    """
    if proposed_action in ("generate_result", "finish"):
        return False
    history: List[Dict[str, Any]] = state.get("planner_history") or []
    recent = history[-LOOP_DETECTION_WINDOW:]
    counts = Counter(step.get("action") for step in recent)
    return counts.get(proposed_action, 0) >= LOOP_DETECTION_REPEAT


def resolve_planner_action(
    state: AgentState,
    llm_action: str,
    *,
    last_observation: Dict[str, Any],
) -> tuple[str, str]:
    """Merge LLM choice with orchestrator plan based on orchestration mode."""
    mode: OrchestrationMode = state.get("orchestration_mode", "AUTO_PLAN")  # type: ignore[assignment]
    plan = state.get("execution_plan") or []
    next_planned = get_next_planned_action(plan)

    # Loop breaker runs before mode logic so it also applies in EXPLORE.
    if detect_action_loop(state, llm_action):
        forced = _next_pending_excluding(plan, llm_action)
        if forced:
            return forced, f"loop detected on '{llm_action}' — forcing plan step '{forced}'"
        return "generate_result", f"loop detected on '{llm_action}' — forcing generate_result"

    if mode == "EXPLORE":
        return llm_action, "EXPLORE mode — LLM action accepted"

    if _should_allow_error_override(last_observation, llm_action):
        return llm_action, "error recovery override"

    if llm_action in ("generate_result", "finish") and _all_workers_done(plan):
        return llm_action, "all worker steps complete"

    if not next_planned:
        return llm_action, "no pending plan steps"

    if mode == "FIXED":
        if llm_action != next_planned:
            return next_planned, f"FIXED mode — aligned to plan step '{next_planned}'"
        return llm_action, "FIXED mode — matches plan"

    # AUTO_PLAN: prefer plan unless LLM explicitly diverges with a valid alternate
    if llm_action == next_planned:
        return llm_action, "AUTO_PLAN — matches plan"
    if llm_action in ("generate_result", "finish") and not _all_workers_done(plan):
        return next_planned, f"AUTO_PLAN — blocked early finish, next plan step '{next_planned}'"
    return llm_action, "AUTO_PLAN — LLM adapted plan"


def _next_pending_excluding(plan: List[PlanStep], skip_action: str) -> str | None:
    """Next pending worker step whose action differs from ``skip_action``."""
    for step in plan:
        if step.get("status") != "pending":
            continue
        action = step.get("action")
        if action in ("generate_result", "finish"):
            continue
        if action != skip_action:
            return action
    return None


def _all_workers_done(plan: List[PlanStep]) -> bool:
    for step in plan:
        if step.get("action") in ("generate_result", "finish"):
            continue
        if step.get("status") == "pending":
            return False
    return True


def _should_allow_error_override(observation: Dict[str, Any], llm_action: str) -> bool:
    if not observation:
        return False
    if observation.get("status") != "error":
        return False
    failed_action = observation_to_action(observation)
    if not failed_action:
        return True
    return llm_action != failed_action
