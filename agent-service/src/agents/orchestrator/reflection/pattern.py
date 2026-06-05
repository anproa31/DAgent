"""Reflection gating (solution.md §2).

Reflection is bounded three ways:
1. Skip entirely for simple RETRIEVAL queries.
2. One-way quality gate — only reflect when the report scores below threshold.
3. Hard cap on passes is enforced in ``reflection_node``.
"""

from __future__ import annotations

import re

from agents.orchestrator.reflection.helpers import flatten_report_content
from agents.shared.state import AgentState
from config.settings import REFLECTION_QUALITY_THRESHOLD

# Markers of an under-developed report — drag the quality score down.
_PLACEHOLDER_PATTERNS = (
    re.compile(r"\bTODO\b", re.I),
    re.compile(r"\bplaceholder\b", re.I),
    re.compile(r"\b(lorem ipsum|tbd|n/?a)\b", re.I),
    re.compile(r"\bunavailable\b", re.I),
)

_ANALYTICAL_SECTIONS = ("insight", "analysis", "finding", "recommend", "trend", "summary")


def evaluate_report_quality(report_content: list) -> float:
    """Heuristic completeness/coherence score in [0, 1] (solution.md §2 Fix 2).

    Deterministic so the gate adds no extra LLM call. Higher is better; a
    report that scores at/above the threshold needs no reflection.
    """
    text = flatten_report_content(report_content)
    if not text or text.startswith("("):  # "(No report content generated)" etc.
        return 0.0

    score = 0.4

    # Substance: a real report has some length.
    length = len(text)
    if length >= 1200:
        score += 0.3
    elif length >= 400:
        score += 0.2
    elif length >= 150:
        score += 0.1

    # Structure: headings / multiple sections signal coherence.
    if text.count("#") >= 2 or text.count("\n\n") >= 2:
        score += 0.15

    # Analytical depth: at least one analysis-style section.
    lowered = text.lower()
    if any(marker in lowered for marker in _ANALYTICAL_SECTIONS):
        score += 0.15

    # Penalise placeholders / "unavailable" filler.
    if any(p.search(text) for p in _PLACEHOLDER_PATTERNS):
        score -= 0.3

    return max(0.0, min(1.0, score))


def should_run_reflection(state: AgentState) -> bool:
    """Reflect only for ANALYTICAL reports that fall below the quality gate."""
    if state.get("intent", "ANALYTICAL") == "RETRIEVAL":
        return False
    score = evaluate_report_quality(state.get("report_content") or [])
    return score < REFLECTION_QUALITY_THRESHOLD
