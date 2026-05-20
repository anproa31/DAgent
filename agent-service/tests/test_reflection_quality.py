"""Tests for the reflection quality gate (solution.md §2 Fix 2)."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agents.reflection.pattern import evaluate_report_quality, should_run_reflection  # noqa: E402


def test_empty_report_scores_zero():
    assert evaluate_report_quality([]) == 0.0


def test_rich_report_scores_high():
    content = [
        {"type": "markdown", "content": "# Analysis\n\n## Key Findings\n" + ("Revenue grew. " * 80)},
        {"type": "markdown", "content": "## Recommendations\n\nFocus on trend in segment A."},
    ]
    assert evaluate_report_quality(content) >= 0.75


def test_placeholder_report_penalised():
    content = [{"type": "markdown", "content": "TODO: add analysis here. " * 30}]
    assert evaluate_report_quality(content) < 0.75


def test_should_skip_reflection_for_retrieval():
    assert should_run_reflection({"intent": "RETRIEVAL"}) is False


def test_should_run_reflection_for_weak_analytical():
    assert should_run_reflection({"intent": "ANALYTICAL", "report_content": []}) is True


def test_should_skip_reflection_for_strong_analytical():
    content = [
        {"type": "markdown", "content": "# Analysis\n\n## Key Findings\n" + ("Detailed insight. " * 90)},
        {"type": "markdown", "content": "## Recommendations\n\nActionable trend recommendation."},
    ]
    assert should_run_reflection({"intent": "ANALYTICAL", "report_content": content}) is False
