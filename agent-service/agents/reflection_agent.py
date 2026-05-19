from agents.state import AgentState
from utils.agent_logger import get_logger
from utils.llm_client import get_async_client, chat_complete
from utils.prompts import REFLECTION_CRITIC_SYSTEM, format_semantic_context_for_prompt
import json
import re

logger = get_logger("reflection_agent")


MAX_REPLAN_COUNT = 3


async def reflection_agent_node(state: AgentState) -> dict:
    """Critique the generated report against original query.

    Returns pass/fail decision with feedback. If failed, orchestrator will re-plan.
    """
    query = state.get("query", "")
    report_content = state.get("report_content", [])
    intent = state.get("intent", "ANALYTICAL")
    replan_count = state.get("replan_count", 0)

    logger.info("enter replan_count=%d", replan_count)

    # Hard stop: exceeded max re-plan attempts
    if replan_count >= MAX_REPLAN_COUNT:
        logger.warning("max replan count reached (%d), forcing pass", replan_count)
        return {
            "current_agent": "reflection",
            "reflection_passed": True,
            "reflection_feedback": f"Report accepted after {MAX_REPLAN_COUNT} revision attempts.",
            "agent_steps": state.get("agent_steps", []) + ["reflection"],
        }

    # Convert report content to text for critique
    report_text = _flatten_report_content(report_content)

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
        {"role": "user", "content": f"Report to evaluate:\n{report_text}"},
    ]

    try:
        raw = await chat_complete(client, model, messages, temperature=0.2, log_tag="reflection_agent")
    except Exception as e:
        logger.error("LLM error: %s", e)
        # Default to pass on error to avoid infinite loops
        return {
            "current_agent": "reflection",
            "reflection_passed": True,
            "reflection_feedback": f"Reflection skipped due to error: {e}",
            "agent_steps": state.get("agent_steps", []) + ["reflection"],
        }

    # Parse JSON response
    decision = _parse_reflection_response(raw)

    passed = decision.get("pass", True)
    feedback = decision.get("feedback", "")
    replan_reason = decision.get("replan_reason", "")

    logger.info("exit pass=%s feedback=%r", passed, (feedback[:100] if feedback else ""))

    return {
        "current_agent": "reflection",
        "reflection_passed": passed,
        "reflection_feedback": feedback,
        "reflection_replan_reason": replan_reason if not passed else "",
        "agent_steps": state.get("agent_steps", []) + ["reflection"],
    }


def _flatten_report_content(report_content: list) -> str:
    """Convert report_content list to plain text for critique."""
    if not report_content:
        return "(No report content generated)"

    sections = []
    for item in report_content:
        if isinstance(item, dict):
            if item.get("type") == "markdown":
                sections.append(item.get("content", ""))
            elif item.get("type") == "table":
                sections.append(f"[Table: {item.get('title', 'data')}]")
            elif item.get("type") == "image":
                sections.append(f"[Chart: {item.get('title', 'visualization')}]")
        elif isinstance(item, str):
            sections.append(item)

    return "\n\n".join(sections) if sections else "(Empty report)"


def _parse_reflection_response(raw: str) -> dict:
    """Parse JSON from reflection response."""
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass

    # Fallback: look for explicit pass/fail keywords
    raw_lower = raw.lower()
    if "fail" in raw_lower or "reject" in raw_lower or "incomplete" in raw_lower:
        return {"pass": False, "feedback": raw[:500]}

    return {"pass": True, "feedback": raw[:500]}


def route_after_reflection(state: AgentState) -> str:
    """Route based on reflection decision."""
    if state.get("reflection_passed"):
        logger.info("route reflection passed -> END")
        return "final_report"

    # Failed reflection → re-plan (back to planner)
    replan_count = state.get("replan_count", 0)
    if replan_count >= MAX_REPLAN_COUNT:
        logger.warning("route max replan reached -> END")
        return "final_report"

    logger.info("route reflection failed -> planner")
    return "planner"
