"""Central Orchestrator: reasoning, planning, routing, reflection.

The user interacts only with the Orchestrator. Specialized agents are invoked
via routing and never exposed directly to the user API.

Architecture (diagram #1):
  User → Orchestrator (reason / plan / route / reflect) → Specialized Agents
  Each agent: scope & instructions | knowledge | tools
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from agents.shared.agent_anatomy import LoopPhase
from agents.shared.specialized_agent import PLANNER_ACTION_TO_AGENT, get_agent_def
from agents.shared.state import AgentState


@dataclass
class ReasoningResult:
    """Output of the reasoning phase (intent + context)."""

    intent: str
    execution_mode: str
    orchestration_mode: str
    language: str
    schema_info: str
    enhanced_context: str
    datasources: List[Dict[str, Any]]


@dataclass
class PlanningResult:
    """Output of the planning phase."""

    pipeline: List[str]
    execution_plan: List[Dict[str, Any]]


class Orchestrator:
    """Hub between the user and specialized worker agents."""

    # --- Routing (called by LangGraph conditional edges) ---

    @staticmethod
    def route(action: str) -> str:
        """Map a planner action to a specialized agent graph node."""
        return PLANNER_ACTION_TO_AGENT.get(action, "exec")

    @staticmethod
    def route_after_planner(state: AgentState) -> str:
        action = state.get("current_action", "exec")
        target = Orchestrator.route(action)
        return target

    @staticmethod
    def describe_route(action: str) -> str:
        agent = get_agent_def(action)
        if agent:
            return f"{action} → {agent.graph_node} ({agent.description})"
        return f"{action} → {PLANNER_ACTION_TO_AGENT.get(action, 'exec')}"

    # --- Reflection contract (implemented by reflection_node) ---

    @staticmethod
    def reflection_entry(state: AgentState) -> Dict[str, Any]:
        """Mark reflection phase — critic runs in agents/reflection/nodes.py."""
        return {
            "loop_phase": LoopPhase.BRAIN.value,
            "current_agent": "orchestrator:reflection",
        }

    @staticmethod
    def should_accept_report(state: AgentState) -> bool:
        return not state.get("reflection_needs_rerun") and not state.get("needs_refinement")
