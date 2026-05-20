"""Reflection quality gate: critique report and optionally trigger re-plan."""

from __future__ import annotations

from agents.reflection.helpers import (
    build_data_context_from_history,
    extract_data_discovery_error_from_history,
    flatten_report_content,
    is_schema_complaint,
    parse_reflection_response,
)
from agents.reflection.memory import record_trajectory
from agents.shared.state import AgentState
from utils.agent_logger import get_logger
from utils.llm_client import chat_complete, get_async_client
from utils.prompts import REFLECTION_CRITIC_SYSTEM, format_semantic_context_for_prompt

logger = get_logger("reflection_agent")

MAX_REPLAN_COUNT = 4


async def reflection_agent_node(state: AgentState) -> dict:
    query = state.get("query", "")
    report_content = state.get("report_content", [])
    intent = state.get("intent", "ANALYTICAL")
    replan_count = state.get("replan_count", 0)
    planner_history = state.get("planner_history", [])

    logger.info("enter replan_count=%d", replan_count)

    if replan_count >= MAX_REPLAN_COUNT:
        logger.warning("max replan count reached (%d), forcing pass", replan_count)
        return {
            "current_agent": "reflection",
            "reflection_passed": True,
            "reflection_feedback": f"Report accepted after {MAX_REPLAN_COUNT} revision attempts.",
            "agent_steps": state.get("agent_steps", []) + ["reflection"],
        }

    data_error = extract_data_discovery_error_from_history(planner_history)
    if data_error:
        logger.info("worker reported data unavailable: %s — accepting", data_error[:80])
        return {
            "current_agent": "reflection",
            "reflection_passed": True,
            "reflection_feedback": f"Report accepted. Worker confirmed data limitation: {data_error}",
            "agent_steps": state.get("agent_steps", []) + ["reflection"],
        }

    report_text = flatten_report_content(report_content)
    data_context = build_data_context_from_history(planner_history)

    client = get_async_client(state.get("base_url", ""), state.get("api_key", ""))
    model = state.get("model", "")
    ctx = format_semantic_context_for_prompt(state.get("enhanced_context", ""))

    system_prompt = REFLECTION_CRITIC_SYSTEM.format(
        context=ctx,
        query=query,
        intent=intent,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Report to evaluate:\n{report_text}\n\n## Data Context (from execution):\n{data_context}",
        },
    ]

    try:
        raw = await chat_complete(client, model, messages, temperature=0.2, log_tag="reflection_agent")
    except Exception as e:
        logger.error("LLM error: %s", e)
        return {
            "current_agent": "reflection",
            "reflection_passed": True,
            "reflection_feedback": f"Reflection skipped due to error: {e}",
            "agent_steps": state.get("agent_steps", []) + ["reflection"],
        }

    decision = parse_reflection_response(raw)

    passed = decision.get("pass", True)
    feedback = decision.get("feedback", "")
    replan_reason = decision.get("replan_reason", "")

    if not passed and replan_reason:
        if is_schema_complaint(replan_reason, state.get("datasources", [])):
            logger.info(
                "critic rejected for schema reason but worker has authority: %s",
                replan_reason[:100],
            )
            passed = True
            feedback = f"Report accepted. {replan_reason} (Worker confirmed unavailable)"

    logger.info("exit pass=%s feedback=%r", passed, (feedback[:100] if feedback else ""))

    record_trajectory(
        query=query,
        intent=intent,
        pipeline=state.get("pipeline", []),
        critic_passed=passed,
        critic_feedback=feedback,
        data_error=data_error,
        replan_count=replan_count,
        planner_steps=planner_history,
    )

    return {
        "current_agent": "reflection",
        "reflection_passed": passed,
        "reflection_feedback": feedback,
        "reflection_replan_reason": replan_reason if not passed else "",
        "agent_steps": state.get("agent_steps", []) + ["reflection"],
    }


def route_after_reflection(state: AgentState) -> str:
    if state.get("reflection_passed"):
        logger.info("route reflection passed -> END")
        return "final_report"

    replan_count = state.get("replan_count", 0)
    if replan_count >= MAX_REPLAN_COUNT:
        logger.warning("route max replan reached -> END")
        return "final_report"

    logger.info("route reflection failed -> orchestrator (re-plan pipeline)")
    return "orchestrator"
