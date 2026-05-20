"""Planner routing helpers."""

from __future__ import annotations

from agents.shared.state import AgentState
from utils.agent_logger import get_logger

logger = get_logger("planner")


def route_after_planner(state: AgentState) -> str:
    """Route to the agent specified by the planner's current_action."""
    action = state.get("current_action", "exec")

    action_to_node = {
        "exec": "exec",
        "sql": "sql",
        "python": "python",
        "discover_data": "web_discover",
        "eda": "eda",
        "insight": "insight",
        "viz": "viz",
        "generate_result": "final_report",
        "finish": "final_report",
    }

    target = action_to_node.get(action, "exec")
    logger.info("route action=%s -> %s", action, target)
    return target
