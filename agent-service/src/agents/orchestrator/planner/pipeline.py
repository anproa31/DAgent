"""Pipeline normalization and reflection-driven adjustments."""

from __future__ import annotations

from typing import List

from agents.orchestrator.planner.plan import OrchestrationMode, detect_explore_intent

_VALID_STEPS = frozenset({"exec", "sql", "python", "eda", "insight", "viz"})


def normalise_pipeline(
    pipeline: list,
    execution_mode: str,
    intent: str,
    orchestration_mode: OrchestrationMode = "FIXED",
    query: str = "",
) -> list:
    """Collapse the data step to a generic ``exec`` and keep sensible follow-ups.

    The concrete SQL-vs-Python decision is deferred to the runtime exec node
    (agents/executor/exec_router.py), so the plan always starts with ``exec``
    regardless of the orchestrator's ``execution_mode`` hint.
    """
    pipeline = [step for step in pipeline if step in _VALID_STEPS]
    pipeline = [step for step in pipeline if step not in ("sql", "python", "exec")]
    pipeline.insert(0, "exec")

    if intent == "RETRIEVAL" and orchestration_mode == "FIXED" and not detect_explore_intent(query):
        return pipeline[:1]
    return pipeline


def adjust_pipeline_for_reflection(
    pipeline: list, feedback: str, intent: str, execution_mode: str
) -> list:
    """Add missing agents suggested by reflection feedback."""
    feedback_lower = feedback.lower()
    additions = []

    if "eda" in feedback_lower or "exploratory" in feedback_lower or "distribution" in feedback_lower:
        if "eda" not in pipeline:
            additions.append("eda")

    if "insight" in feedback_lower or "business" in feedback_lower or "actionable" in feedback_lower:
        if "insight" not in pipeline:
            additions.append("insight")

    if "viz" in feedback_lower or "chart" in feedback_lower or "visual" in feedback_lower:
        if "viz" not in pipeline:
            additions.append("viz")

    for agent in additions:
        if agent not in pipeline:
            pipeline.append(agent)

    return normalise_pipeline(pipeline, execution_mode, intent, orchestration_mode="EXPLORE")
