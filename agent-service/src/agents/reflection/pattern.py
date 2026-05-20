"""Skip reflection for simple RETRIEVAL queries (agent-patterns guidance)."""

from __future__ import annotations

from agents.shared.state import AgentState


def should_run_reflection(state: AgentState) -> bool:
    return state.get("intent", "ANALYTICAL") != "RETRIEVAL"
