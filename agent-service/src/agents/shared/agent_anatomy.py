"""Agent anatomy: perceive → brain → act → observe loop and stop conditions.

Maps to the ByteByteGo agent diagram (memory, tools, guardrails plug in at each phase).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from agents.shared.state import AgentState
from config.settings import (
    FORCED_EXIT_THRESHOLD,
    MAX_PLANNER_STEPS,
    MAX_RUN_BUDGET_UNITS,
)


class LoopPhase(str, Enum):
    """Explicit phases in the agent loop."""

    PERCEIVE = "perceive"
    BRAIN = "brain"
    ACT = "act"
    OBSERVE = "observe"


class StopReason(str, Enum):
    """Why the agent loop stopped."""

    DONE = "done"
    MAX_ITERS = "max_iters"
    BUDGET = "budget"
    FORCED_EXIT = "forced_exit"
    USER_CANCELLED = "user_cancelled"
    ERROR = "error"


@dataclass(frozen=True)
class StopDecision:
    """Result of evaluating loop stop conditions."""

    should_stop: bool
    reason: Optional[StopReason] = None
    forced_action: Optional[str] = None
    message: str = ""


def init_run_budget(*, limit: int | None = None) -> Dict[str, Any]:
    """Initialize per-run action budget (planner steps + tool calls)."""
    return {
        "used": 0,
        "limit": limit or MAX_RUN_BUDGET_UNITS,
        "exhausted": False,
    }


def consume_budget(state: AgentState, units: int = 1) -> Dict[str, Any]:
    """Increment run budget and return updated budget dict."""
    budget = dict(state.get("run_budget") or init_run_budget())
    budget["used"] = int(budget.get("used", 0)) + units
    budget["exhausted"] = budget["used"] >= int(budget.get("limit", MAX_RUN_BUDGET_UNITS))
    return budget


def is_budget_exhausted(state: AgentState) -> bool:
    budget = state.get("run_budget") or {}
    return bool(budget.get("exhausted"))


def evaluate_stop(state: AgentState) -> StopDecision:
    """Check done / max_iters / budget before the brain plans the next step."""
    if state.get("done"):
        return StopDecision(True, StopReason.DONE, message="Run already marked done.")

    if is_budget_exhausted(state):
        return StopDecision(
            True,
            StopReason.BUDGET,
            forced_action="generate_result",
            message="Run budget exhausted — compiling report.",
        )

    step_index = state.get("planner_step_index", 0)
    if step_index >= MAX_PLANNER_STEPS:
        return StopDecision(
            True,
            StopReason.MAX_ITERS,
            forced_action="generate_result",
            message=f"Max planner steps ({MAX_PLANNER_STEPS}) reached.",
        )

    completed = state.get("completed_actions") or []
    has_data = any(a in ("exec", "sql", "python") for a in completed)
    if step_index >= FORCED_EXIT_THRESHOLD and has_data:
        return StopDecision(
            True,
            StopReason.FORCED_EXIT,
            forced_action="generate_result",
            message=f"Forced exit at step {step_index} with data available.",
        )

    return StopDecision(False)


def phase_update(phase: LoopPhase) -> Dict[str, Any]:
    """State patch marking the current loop phase."""
    return {"loop_phase": phase.value, "current_agent": phase.value}
