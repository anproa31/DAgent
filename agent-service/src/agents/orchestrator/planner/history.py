"""Planner history compression and RL suggestion formatting."""

from __future__ import annotations

from typing import Any, Dict


def compress_planner_history(history: list, keep_last_n: int = 5) -> str:
    """Compress planner history for prompt context."""
    if not history:
        return "(no prior steps)"

    recent = history[-keep_last_n:]
    lines = []
    for i, step in enumerate(recent):
        thought = step.get("thought", "")[:100]
        action = step.get("action", "")
        obs = step.get("observation", {})
        obs_summary = obs.get("summary", "(no summary)") if obs else "(pending)"
        lines.append(f"Step {i+1}: thought={thought}... | action={action} | observation={obs_summary}")

    return "\n".join(lines)


def format_rl_suggestion(suggestion: Dict[str, Any]) -> str:
    """Format RL policy suggestion for planner prompt."""
    source = suggestion.get("source", "unknown")
    pipeline = suggestion.get("pipeline", [])
    confidence = suggestion.get("confidence", 0.0)
    return f"Source: {source} | Pipeline: {pipeline} | Confidence: {confidence:.2f}"
