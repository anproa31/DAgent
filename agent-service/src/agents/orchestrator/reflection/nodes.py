"""Reflection node powered by agent-patterns ReflectionAgent."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, List

from agents.orchestrator.reflection.analytics_reflection_agent import get_analytics_reflection_agent
from agents.orchestrator.core import Orchestrator
from agents.orchestrator.reflection.helpers import build_data_context_from_history, flatten_report_content
from agents.orchestrator.reflection.memory import record_trajectory
from agents.orchestrator.reflection.pattern import should_run_reflection
from agents.shared.state import AgentState
from config.settings import MAX_REFLECTION_PASSES, MAX_REFLECTION_RERUNS
from agents.orchestrator.planner.plan import update_plan_from_reflection
from utils.agent_logger import get_logger
from utils.prompts import format_semantic_context_for_prompt, format_language_rule

logger = get_logger("reflection")

# Feedback signalling a defect text-refinement cannot fix — needs a worker rerun.
_SERIOUS_ISSUE_PATTERNS = (
    re.compile(r"\b(missing|absent|no)\s+(data|chart|table|visuali[sz]ation|figure)\b", re.I),
    re.compile(r"\b(wrong|incorrect|mismatch(?:ed)?|inconsistent)\s+(number|value|figure|total|count)", re.I),
    re.compile(r"\bdoes not (answer|address)\b", re.I),
    re.compile(r"\b(requested|expected)\s+(chart|plot|visuali[sz]ation)\b.*\b(not|missing)\b", re.I),
)


async def reflection_node(state: AgentState) -> dict:
    """Run agent-patterns reflect → refine on the compiled report.

    Bounded by ``MAX_REFLECTION_PASSES`` (solution.md §2 Fix 1). When the
    critic finds a defect text can't fix, flag a single targeted rerun back
    through the planner (solution.md §2 Fix 3).
    """
    report_content = state.get("report_content") or []
    report_text = flatten_report_content(report_content)
    prior_cycles = state.get("reflection_cycle", 0)

    reflection_patch = Orchestrator.reflection_entry(state)

    # Hard limit: never refine more than MAX_REFLECTION_PASSES times per run.
    if prior_cycles >= MAX_REFLECTION_PASSES:
        logger.info("reflection hard limit reached (%d) — stopping", prior_cycles)
        return {
            **reflection_patch,
            "current_agent": "reflection",
            "reflection": "Reflection passes exhausted; accepting current report.",
            "reflection_needs_rerun": False,
            "agent_steps": state.get("agent_steps", []) + ["reflection"],
        }

    # Cap the agent's internal cycles to the remaining budget.
    remaining = max(1, MAX_REFLECTION_PASSES - prior_cycles)
    max_cycles = min(state.get("max_reflection_cycles", 1) or 1, remaining)

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
            "reflection_needs_rerun": False,
            "agent_steps": state.get("agent_steps", []) + ["reflection"],
        }

    refined_text = result.get("final_answer") or report_text
    updated_content = _merge_refined_report(report_content, refined_text)
    feedback = result.get("reflection", "") or ""

    record_trajectory(
        query=state.get("query", ""),
        intent=state.get("intent", "ANALYTICAL"),
        pipeline=state.get("pipeline", []),
        critic_passed=not result.get("needs_refinement", False),
        critic_feedback=feedback,
        data_error=None,
        replan_count=result.get("reflection_cycle", 0),
        planner_steps=state.get("planner_history", []),
    )

    rerun_count = state.get("rerun_count", 0)
    serious = _detect_serious_issue(feedback) and bool(result.get("needs_refinement", False))
    can_rerun = serious and rerun_count < MAX_REFLECTION_RERUNS

    patch: dict = {
        "current_agent": "reflection",
        "report_content": updated_content,
        "reflection": feedback,
        "refined_output": result.get("refined_output") or refined_text,
        "reflection_cycle": prior_cycles + max(1, result.get("reflection_cycle", 0)),
        "needs_refinement": result.get("needs_refinement", False),
        "continue_reflection": result.get("continue_reflection", False),
        "reflection_needs_rerun": can_rerun,
        "agent_steps": state.get("agent_steps", []) + ["reflection"],
    }

    if can_rerun:
        new_plan = update_plan_from_reflection(
            state.get("execution_plan") or [],
            feedback,
            state.get("execution_mode", "sql"),
        )
        patch["execution_plan"] = new_plan
        patch["rerun_count"] = rerun_count + 1
        patch["done"] = False  # let the planner pick up the inserted steps
        logger.info("reflection requesting targeted rerun (#%d)", rerun_count + 1)

    logger.info(
        "reflection done cycles=%d refined=%s rerun=%s",
        patch["reflection_cycle"],
        bool(result.get("refined_output")),
        can_rerun,
    )

    return patch


def route_after_final_report(state: AgentState) -> str:
    if not should_run_reflection(state):
        logger.info("route final_report -> END (skip reflection)")
        return "done"
    logger.info("route final_report -> reflection (agent-patterns)")
    return "reflection"


def reflection_router(state: AgentState) -> str:
    """After reflection: targeted rerun via planner, else finish (solution.md §2 Fix 3)."""
    if state.get("reflection_needs_rerun") and state.get("rerun_count", 0) <= MAX_REFLECTION_RERUNS:
        logger.info("route reflection -> planner (targeted rerun)")
        return "planner"
    logger.info("route reflection -> END")
    return "done"


def _detect_serious_issue(feedback: str) -> bool:
    if not feedback:
        return False
    return any(p.search(feedback) for p in _SERIOUS_ISSUE_PATTERNS)


def _build_reflection_task(state: AgentState) -> str:
    ctx = format_semantic_context_for_prompt(state.get("enhanced_context", ""))
    data_context = build_data_context_from_history(state.get("planner_history", []))
    return (
        f"User query: {state.get('query', '')}\n"
        f"Intent: {state.get('intent', 'ANALYTICAL')}\n"
        f"{format_language_rule(state.get('language', 'en'))}\n\n"
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
