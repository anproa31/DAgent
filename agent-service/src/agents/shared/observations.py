"""Structured observations passed from worker agents back to the planner."""

from __future__ import annotations

from typing import Any, Dict, Optional


def create_observation(
    agent_name: str,
    status: str,
    summary: str,
    artifacts: Dict[str, Any],
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a structured observation for the planner."""
    return {
        "agent": agent_name,
        "status": status,
        "summary": summary,
        "artifacts": artifacts,
        "error": error,
    }
