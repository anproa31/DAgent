"""SQL generation agent with human-in-the-loop approval."""

from __future__ import annotations

import re

from langgraph.types import interrupt

from agents.shared.observations import create_observation
from agents.shared.state import AgentState
from agents.shared.worker_context import build_worker_user_message, sanitize_sql_explanation
from orchestration.streaming import make_delta_emitter
from utils.agent_logger import get_logger
from utils.llm_client import chat_complete, get_async_client
from utils.prompts import SQL_AGENT_SYSTEM, format_semantic_context_for_prompt, format_language_rule
from utils.sql_sanitize import clean_sql_for_execution, extract_sql_from_llm_response

logger = get_logger("sql_agent")


async def sql_agent_node(state: AgentState) -> dict:
    logger.info("enter query=%r", state["query"][:80])

    # Short-circuit: SQL already approved and data fetched — skip regeneration.
    # This prevents the planner from triggering a duplicate HITL interrupt when
    # it re-routes to sql after the data is already available.
    if state.get("sql_approved") and state.get("result_var_names"):
        logger.info("SQL already executed — returning cached observation")
        obs = create_observation(
            agent_name="sql",
            status="success",
            summary="SQL already executed — data available in df_result",
            artifacts={"sql_draft": state.get("sql_draft", ""), "sql_approved": True},
            error=None,
        )
        return {
            "current_agent": "sql",
            "sql_approved": True,
            "agent_steps": state.get("agent_steps", []) + ["sql"],
            "last_observation": obs,
        }

    client = get_async_client(state.get("base_url", ""), state.get("api_key", ""))
    model = state.get("model", "")
    schema = state.get("schema_info", "No schema available")
    ctx = format_semantic_context_for_prompt(state.get("enhanced_context", ""))

    system_prompt = SQL_AGENT_SYSTEM.format(
        context=ctx,
        schema=schema,
        language_rule=format_language_rule(state.get("language", "en")),
    )

    user_edited_sql = state.get("sql_draft", "")
    rejection_reason = state.get("sql_rejection_reason", "")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": build_worker_user_message(state, "sql")},
    ]

    if rejection_reason and user_edited_sql:
        messages.append({"role": "assistant", "content": f"SQL: {user_edited_sql}"})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"The previous SQL was rejected with feedback: {rejection_reason}\n"
                    f"User provided this edited SQL: {user_edited_sql}\n"
                    "Please regenerate a corrected SQL query that addresses the feedback."
                ),
            }
        )
    elif rejection_reason:
        messages.append(
            {
                "role": "user",
                "content": (
                    f"The previous SQL was rejected: {rejection_reason}\n"
                    "Please generate a corrected SQL query."
                ),
            }
        )

    try:
        raw = await chat_complete(
            client,
            model,
            messages,
            temperature=0.1,
            log_tag="sql_agent",
            on_delta=make_delta_emitter(state.get("run_id", ""), "sql"),
        )
    except Exception as e:
        logger.error("LLM error: %s", e)
        obs = create_observation(
            agent_name="sql",
            status="error",
            summary=f"SQL generation failed: {e}",
            artifacts={"sql_draft": "", "sql_explanation": ""},
            error=str(e),
        )
        return {
            "current_agent": "sql",
            "error": f"SQL generation failed: {e}",
            "agent_steps": state.get("agent_steps", []) + ["sql"],
            "last_observation": obs,
        }

    sql_draft = ""
    sql_explanation = ""

    exp_match = re.search(r"EXPLANATION:\s*(.+)", raw, re.DOTALL | re.IGNORECASE)
    sql_draft = clean_sql_for_execution(extract_sql_from_llm_response(raw))

    if exp_match:
        sql_explanation = sanitize_sql_explanation(exp_match.group(1).strip())

    logger.info("generated SQL:\n%s", sql_draft)

    approval = interrupt(
        {
            "type": "sql_review",
            "sql": sql_draft,
            "explanation": sql_explanation,
            "query": state["query"],
        }
    )

    approved = approval.get("approved", False)
    edited_sql = clean_sql_for_execution(approval.get("sql", sql_draft) or "")
    rejection_reason_new = approval.get("reason", "")
    logger.info("HITL approval=%s edited=%s", approved, edited_sql != sql_draft)

    if not approved:
        obs = create_observation(
            agent_name="sql",
            status="rejected",
            summary=f"SQL rejected: {rejection_reason_new}",
            artifacts={"sql_draft": edited_sql or sql_draft, "sql_explanation": sql_explanation},
            error=rejection_reason_new,
        )
        return {
            "current_agent": "sql",
            "sql_draft": edited_sql or sql_draft,
            "sql_explanation": sql_explanation,
            "sql_approved": False,
            "sql_rejection_reason": rejection_reason_new,
            "agent_steps": state.get("agent_steps", []) + ["sql"],
            "last_observation": obs,
        }

    obs = create_observation(
        agent_name="sql",
        status="success",
        summary=f"SQL approved: {sql_explanation[:50]}...",
        artifacts={
            "sql_draft": edited_sql,
            "sql_explanation": sql_explanation,
            "sql_approved": True,
        },
        error=None,
    )

    return {
        "current_agent": "sql",
        "sql_draft": edited_sql,
        "sql_explanation": sql_explanation,
        "sql_approved": True,
        "sql_rejection_reason": "",
        "agent_steps": state.get("agent_steps", []) + ["sql"],
        "last_observation": obs,
    }


def route_after_sql(state: AgentState) -> str:
    if state.get("sql_approved"):
        return "code_executor"
    return "planner"
