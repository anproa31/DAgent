"""Central Orchestrator facade: reasoning, planning, routing, reflection.

The user interacts only with the Orchestrator. Specialized worker agents are
invoked via routing and never exposed directly to the user API.

Architecture (diagram #1) — the four orchestrator capabilities live together
under ``orchestration/orchestrator/``:
  - Reasoning + initial Planning : ``node.py`` (orchestrator_node)
  - Planning (per-step brain)     : ``planner/``
  - Routing (action → worker)     : ``routing.py`` + ``Orchestrator.route``
  - Reflection                    : ``reflection/``

Each worker agent carries: scope & instructions | knowledge | tools
(see agents/shared/specialized_agent.py).
"""

from __future__ import annotations

from typing import Any, Dict

from agents.shared.agent_anatomy import LoopPhase
from agents.shared.specialized_agent import PLANNER_ACTION_TO_AGENT, get_agent_def
from agents.shared.state import AgentState


class Orchestrator:
    """Hub between the user and specialized worker agents."""

    # --- Routing (called by LangGraph conditional edges) ---

    @staticmethod
    def route(action: str) -> str:
        """Map a planner action to a specialized agent graph node."""
        return PLANNER_ACTION_TO_AGENT.get(action, "exec")

    @staticmethod
    def describe_route(action: str) -> str:
        agent = get_agent_def(action)
        if agent:
            return f"{action} → {agent.graph_node} ({agent.description})"
        return f"{action} → {PLANNER_ACTION_TO_AGENT.get(action, 'exec')}"

    # --- Reflection contract (implemented by reflection/nodes.py) ---

    @staticmethod
    def reflection_entry(state: AgentState) -> Dict[str, Any]:
        """Mark reflection phase — critic runs in orchestrator/reflection/nodes.py."""
        return {
            "loop_phase": LoopPhase.BRAIN.value,
            "current_agent": "orchestrator:reflection",
        }
