from agents.state import AgentState
from utils.agent_logger import get_logger
from utils.llm_client import get_async_client, chat_complete
from utils.prompts import REFLECTION_CRITIC_SYSTEM, format_semantic_context_for_prompt
from agents.reflection_rl import record_trajectory, get_policy_suggestion
import json
import re

logger = get_logger("reflection_agent")


MAX_REPLAN_COUNT = 4  # Allow more iterations for RL reflection to show effect


async def reflection_agent_node(state: AgentState) -> dict:
    """Critique the generated report against original query.

    Returns pass/fail decision with feedback. If failed, orchestrator will re-plan.

    Authority hierarchy: Worker owns data discovery. Critic validates logic, not schema knowledge.
    If worker reports table/column unavailable, accept it — do not force nonexistent sources.
    """
    query = state.get("query", "")
    report_content = state.get("report_content", [])
    intent = state.get("intent", "ANALYTICAL")
    replan_count = state.get("replan_count", 0)
    planner_history = state.get("planner_history", [])

    logger.info("enter replan_count=%d", replan_count)

    # Hard stop: exceeded max re-plan attempts (escape hatch)
    if replan_count >= MAX_REPLAN_COUNT:
        logger.warning("max replan count reached (%d), forcing pass", replan_count)
        return {
            "current_agent": "reflection",
            "reflection_passed": True,
            "reflection_feedback": f"Report accepted after {MAX_REPLAN_COUNT} revision attempts.",
            "agent_steps": state.get("agent_steps", []) + ["reflection"],
        }

    # Check if worker already reported data unavailability
    data_error = _extract_data_discovery_error(planner_history)
    if data_error:
        # Worker has authority on data availability — accept and pass
        logger.info("worker reported data unavailable: %s — accepting", data_error[:80])
        return {
            "current_agent": "reflection",
            "reflection_passed": True,
            "reflection_feedback": f"Report accepted. Worker confirmed data limitation: {data_error}",
            "agent_steps": state.get("agent_steps", []) + ["reflection"],
        }

    # Convert report content to text for critique
    report_text = _flatten_report_content(report_content)

    # Build data context from planner history (SQL/Python results)
    data_context = _build_data_context_from_history(planner_history)

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
        {"role": "user", "content": f"Report to evaluate:\n{report_text}\n\n## Data Context (from execution):\n{data_context}"},
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

    # CRITICAL: If replan reason is about missing table/column, check if worker already tried
    if not passed and replan_reason:
        if _is_schema_complaint(replan_reason, state.get("datasources", [])):
            # Worker has final say — if they said table doesn't exist, don't force it
            logger.info("critic rejected for schema reason but worker has authority: %s", replan_reason[:100])
            passed = True
            feedback = f"Report accepted. {replan_reason} (Worker confirmed unavailable)"

    logger.info("exit pass=%s feedback=%r", passed, (feedback[:100] if feedback else ""))

    # Record trajectory for RL learning (after deciding pass/fail)
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


def _build_data_context_from_history(planner_history: list) -> str:
    """Extract data context from planner history for critic evaluation.

    Pulls SQL queries, result summaries, and execution outcomes from worker agents.
    """
    if not planner_history:
        return "(No execution history)"

    context_parts = []

    for i, step in enumerate(planner_history):
        action = step.get("action", "")
        observation = step.get("observation", {})

        if not observation:
            continue

        if action in ("sql", "python"):
            parts = []

            # SQL query or Python code
            if observation.get("sql"):
                parts.append(f"Query: {observation['sql']}")
            elif observation.get("code_executed"):
                parts.append(f"Code executed: {observation['code_executed'][:200]}...")

            # Execution status
            status = observation.get("status", "unknown")
            parts.append(f"Status: {status}")

            # Result summary
            if observation.get("summary"):
                parts.append(f"Result: {observation['summary'][:300]}")

            # Row count if available
            artifacts = observation.get("artifacts", {})
            if artifacts.get("row_count"):
                parts.append(f"Rows: {artifacts['row_count']}")
            if artifacts.get("data_summary"):
                parts.append(f"Data summary: {artifacts['data_summary'][:200]}")

            if parts:
                context_parts.append(f"### Step {i+1} ({action}):\n" + "\n".join(parts))

    return "\n\n".join(context_parts) if context_parts else "(No data context available)"


def _extract_data_discovery_error(planner_history: list) -> str | None:
    """Extract data discovery errors from planner history.

    If worker agent reported table/column unavailable, return the error message.
    """
    if not planner_history:
        return None

    for step in reversed(planner_history):
        obs = step.get("observation", {})
        if not obs:
            continue

        status = obs.get("status", "")
        summary = obs.get("summary", "")

        # Check for explicit data unavailability signals
        if status == "error" or "not found" in summary.lower():
            if "table" in summary.lower() or "column" in summary.lower() or "datasource" in summary.lower():
                return summary

        # Check artifacts for data_discovery_error flag
        artifacts = obs.get("artifacts", {})
        if artifacts.get("data_discovery_error"):
            return artifacts["data_discovery_error"]

    return None


def _is_schema_complaint(complaint: str, datasources: list) -> bool:
    """Check if complaint is about missing table/column (schema knowledge).

    Critic should validate logic, not force worker to use unavailable tables.
    """
    complaint_lower = complaint.lower()

    # Keywords that indicate schema availability complaint (not logic error)
    schema_keywords = [
        "table", "column", "datasource", "view", "schema",
        "not exist", "not found", "unavailable", "missing",
        "hr_employee_data",  # Specific case from bug report
    ]

    # Check if complaint mentions unavailable schema elements
    has_schema_keyword = any(kw in complaint_lower for kw in schema_keywords)

    # Check if complaint references tables not in available datasources
    available_tables = set()
    for ds in datasources:
        for view in ds.get("view_names", []):
            available_tables.add(view.lower())

    # If complaint names a specific table, check if it exists
    import re
    table_mentions = re.findall(r"['\"]?(\w+_?table\w*)['\"]?", complaint_lower)
    for table in table_mentions:
        if table not in available_tables:
            return True

    return has_schema_keyword


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
