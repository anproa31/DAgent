"""Planner routing — delegates to Orchestrator.route (diagram #1)."""

from __future__ import annotations

from agents.shared.state import AgentState
from agents.orchestrator.core import Orchestrator
from utils.agent_logger import get_logger

logger = get_logger("planner")


def route_after_planner(state: AgentState) -> str:
    """Route to the specialized agent for the planner's current_action."""
    action = state.get("current_action", "exec")
    target = Orchestrator.route(action)
    logger.info("route action=%s -> %s (%s)", action, target, Orchestrator.describe_route(action))
    return target
