"""Reflection node powered by agent-patterns ReflectionAgent."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, List

from agents.reflection.analytics_reflection_agent import get_analytics_reflection_agent
from agents.reflection.helpers import build_data_context_from_history, flatten_report_content
from agents.reflection.memory import record_trajectory
from agents.reflection.pattern import should_run_reflection
from agents.shared.state import AgentState
from utils.agent_logger import get_logger
from utils.prompts import format_semantic_context_for_prompt

logger = get_logger("reflection")


async def reflection_node(state: AgentState) -> dict:
    """Run agent-patterns reflect → refine on the compiled report."""
    report_content = state.get("report_content") or []
    report_text = flatten_report_content(report_content)
    max_cycles = state.get("max_reflection_cycles", 1)

    task = _build_reflection_task(state)
    agent = get_analytics_reflection_agent(
        base_url=state.get("base_url", ""),
        api_key=state.get("api_key", ""),
        model=state.get("model", ""),
        max_reflection_cycles=max_cycles,
    )

    try:
        result = await asyncio.to_thread(agent.run_on_report, task, report_text)
    except Exception as exc:
        logger.error("agent-patterns reflection failed: %s", exc)
        return {
            "current_agent": "reflection",
            "reflection": f"Reflection skipped: {exc}",
            "agent_steps": state.get("agent_steps", []) + ["reflection"],
        }

    refined_text = result.get("final_answer") or report_text
    updated_content = _merge_refined_report(report_content, refined_text)

    record_trajectory(
        query=state.get("query", ""),
        intent=state.get("intent", "ANALYTICAL"),
        pipeline=state.get("pipeline", []),
        critic_passed=not result.get("needs_refinement", False),
        critic_feedback=result.get("reflection", ""),
        data_error=None,
        replan_count=result.get("reflection_cycle", 0),
        planner_steps=state.get("planner_history", []),
    )

    logger.info(
        "reflection done cycles=%d refined=%s",
        result.get("reflection_cycle", 0),
        bool(result.get("refined_output")),
    )

    return {
        "current_agent": "reflection",
        "report_content": updated_content,
        "reflection": result.get("reflection", ""),
        "refined_output": result.get("refined_output") or refined_text,
        "reflection_cycle": result.get("reflection_cycle", 0),
        "needs_refinement": result.get("needs_refinement", False),
        "continue_reflection": result.get("continue_reflection", False),
        "agent_steps": state.get("agent_steps", []) + ["reflection"],
    }


def route_after_final_report(state: AgentState) -> str:
    if not should_run_reflection(state):
        logger.info("route final_report -> END (RETRIEVAL, skip reflection)")
        return "done"
    logger.info("route final_report -> reflection (agent-patterns)")
    return "reflection"


def _build_reflection_task(state: AgentState) -> str:
    ctx = format_semantic_context_for_prompt(state.get("enhanced_context", ""))
    data_context = build_data_context_from_history(state.get("planner_history", []))
    return (
        f"User query: {state.get('query', '')}\n"
        f"Intent: {state.get('intent', 'ANALYTICAL')}\n\n"
        f"Datasource context:\n{ctx}\n\n"
        f"Execution data context:\n{data_context}"
    )


def _merge_refined_report(original: List[Any], refined_text: str) -> List[Any]:
    if not refined_text or refined_text == flatten_report_content(original):
        return original

    try:
        match = re.search(r"\[.*\]", refined_text, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            if isinstance(parsed, list) and parsed:
                return _preserve_assets(parsed, original)
    except Exception:
        pass

    assets = [
        item for item in original if isinstance(item, dict) and item.get("type") in ("table", "image")
    ]
    content: List[Any] = [{"type": "markdown", "content": refined_text.strip()}]
    content.extend(assets)
    return content


def _preserve_assets(refined: List[Any], original: List[Any]) -> List[Any]:
    original_assets = [
        item for item in original if isinstance(item, dict) and item.get("type") in ("table", "image")
    ]
    refined_assets = [
        item for item in refined if isinstance(item, dict) and item.get("type") in ("table", "image")
    ]
    if original_assets and not refined_assets:
        return list(refined) + original_assets
    return refined
