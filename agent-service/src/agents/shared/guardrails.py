"""Policy gate for every action: validate → scope → budget.

Every planner action and tool invocation passes through this gate before execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from agents.shared.agent_anatomy import is_budget_exhausted
from agents.shared.specialized_agent import get_agent_def, is_tool_allowed
from agents.shared.state import AgentState
from config.settings import BUDGET_COST_PER_PLANNER_STEP, BUDGET_COST_PER_TOOL


@dataclass(frozen=True)
class GateResult:
    """Outcome of the guardrail gate."""

    allowed: bool
    reason: str = ""
    normalized_action: Optional[str] = None
    normalized_input: Optional[Dict[str, Any]] = None


VALID_PLANNER_ACTIONS = frozenset(
    {
        "exec",
        "sql",
        "python",
        "eda",
        "insight",
        "viz",
        "generate_result",
        "finish",
    }
)

_ACTION_ALIASES = {
    "final_answer": "generate_result",
    "final": "generate_result",
    "finish": "generate_result",
}


def _normalize_action(action: str) -> str:
    normalized = (action or "").strip().lower().replace(" ", "_")
    return _ACTION_ALIASES.get(normalized, normalized or "exec")


def gate_planner_action(
    state: AgentState,
    action: str,
    action_input: Optional[Dict[str, Any]] = None,
) -> GateResult:
    """Validate → scope → budget for a planner routing decision."""
    action_input = dict(action_input or {})
    normalized = _normalize_action(action)

    # 1. validate
    if normalized not in VALID_PLANNER_ACTIONS:
        return GateResult(
            allowed=True,
            reason=f"Invalid action '{action}' normalized to exec.",
            normalized_action="exec",
            normalized_input=action_input,
        )

    # 2. scope
    agent_def = get_agent_def(normalized)
    if agent_def and action_input.get("task"):
        task = str(action_input["task"])
        if len(task) > 500:
            action_input = {**action_input, "task": task[:497] + "..."}

    # 3. budget
    if is_budget_exhausted(state) and normalized not in ("generate_result", "finish"):
        return GateResult(
            allowed=True,
            reason="Budget exhausted — forcing generate_result.",
            normalized_action="generate_result",
            normalized_input={},
        )

    return GateResult(
        allowed=True,
        normalized_action=normalized,
        normalized_input=action_input,
    )


def gate_tool_call(
    state: AgentState,
    tool_name: str,
    *,
    agent_role: str = "",
) -> GateResult:
    """Validate → scope → budget for a sandbox tool invocation."""
    role = agent_role or state.get("current_agent", "")

    # 1. validate
    if not tool_name:
        return GateResult(allowed=False, reason="Tool name is required.")

    # 2. scope — tool must belong to the active worker agent
    if role and not is_tool_allowed(role, tool_name):
        return GateResult(
            allowed=False,
            reason=f"Tool '{tool_name}' is not in scope for agent '{role}'.",
        )

    # 3. budget
    if is_budget_exhausted(state):
        return GateResult(allowed=False, reason="Run budget exhausted.")

    return GateResult(allowed=True)


def budget_cost_for_planner_step() -> int:
    return BUDGET_COST_PER_PLANNER_STEP


def budget_cost_for_tool() -> int:
    return BUDGET_COST_PER_TOOL
