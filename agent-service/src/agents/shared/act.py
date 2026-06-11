"""Act + observe helpers for worker agents (tool pipeline with guardrails)."""

from __future__ import annotations

from typing import Any, Dict, Optional

from agents.shared.agent_anatomy import LoopPhase, consume_budget
from agents.shared.guardrails import budget_cost_for_tool
from agents.shared.observations import observation_from_tool_result
from agents.shared.state import AgentState
from tools.executor import run_tool
from tools.schemas import ToolResult


async def invoke_tool(
    state: AgentState,
    tool_name: str,
    *,
    agent_role: str,
    **kwargs: Any,
) -> ToolResult:
    """Act phase: guardrail gate → dispatch → exec."""
    return await run_tool(
        state.get("session_id", state.get("run_id", "default")),
        tool_name,
        agent_role=agent_role,
        state=state,
        **kwargs,
    )


def observe_from_tool(
    state: AgentState,
    *,
    agent_role: str,
    tool_name: str,
    result: ToolResult,
    summary: Optional[str] = None,
    next_hint: Optional[str] = None,
    extra_artifacts: Optional[Dict[str, Any]] = None,
    budget_units: int = 1,
) -> Dict[str, Any]:
    """Observe phase: structured observation + budget debit for successful gate."""
    obs = observation_from_tool_result(
        agent_role,
        tool_name,
        result,
        summary=summary,
        next_hint=next_hint,
    )
    if extra_artifacts:
        obs["artifacts"].update(extra_artifacts)

    budget = consume_budget(state, budget_cost_for_tool() * budget_units)

    return {
        "loop_phase": LoopPhase.OBSERVE.value,
        "last_observation": obs,
        "run_budget": budget,
    }
