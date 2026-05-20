"""Tests for agent-patterns ReflectionAgent integration."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agent_patterns.patterns import ReflectionAgent  # noqa: E402

from agents.reflection.analytics_reflection_agent import (  # noqa: E402
    AnalyticsReflectionAgent,
    get_analytics_reflection_agent,
)
from agents.reflection.nodes import route_after_final_report  # noqa: E402
from agents.reflection.pattern import should_run_reflection  # noqa: E402


def test_uses_agent_patterns_reflection_agent():
    assert issubclass(AnalyticsReflectionAgent, ReflectionAgent)


def test_analytics_agent_skips_generate_in_graph():
    agent = AnalyticsReflectionAgent(
        base_url="http://localhost:11434/v1",
        api_key="test",
        model="test-model",
    )
    assert agent.graph is not None
    # Nodes are wired in build_graph — generate_initial is omitted for analytics.
    assert hasattr(agent, "_reflect_on_output")
    assert hasattr(agent, "_refine_output")
    assert not hasattr(agent, "_generate_initial_output") or agent.build_graph.__func__ is not ReflectionAgent.build_graph


def test_agent_cache_reuses_instance():
    a1 = get_analytics_reflection_agent(
        base_url="http://x/v1", api_key="k", model="m", max_reflection_cycles=1
    )
    a2 = get_analytics_reflection_agent(
        base_url="http://x/v1", api_key="k", model="m", max_reflection_cycles=1
    )
    assert a1 is a2


def test_should_skip_reflection_for_retrieval():
    assert should_run_reflection({"intent": "RETRIEVAL"}) is False


def test_should_run_reflection_for_analytical():
    assert should_run_reflection({"intent": "ANALYTICAL"}) is True


def test_route_after_final_report():
    assert route_after_final_report({"intent": "RETRIEVAL"}) == "done"
    assert route_after_final_report({"intent": "ANALYTICAL"}) == "reflection"


def test_run_on_report_invokes_graph():
    agent = AnalyticsReflectionAgent(
        base_url="http://localhost:11434/v1",
        api_key="test",
        model="test-model",
        max_reflection_cycles=1,
    )
    mock_graph = MagicMock()
    mock_graph.invoke.return_value = {
        "final_answer": "Improved report",
        "reflection": "Add more detail",
        "reflection_cycle": 1,
        "needs_refinement": False,
        "refined_output": "Improved report",
    }
    agent.graph = mock_graph

    result = agent.run_on_report("Analyze sales", "Draft report")
    assert result["final_answer"] == "Improved report"
    mock_graph.invoke.assert_called_once()
    call_state = mock_graph.invoke.call_args[0][0]
    assert call_state["input_task"] == "Analyze sales"
    assert call_state["initial_output"] == "Draft report"
