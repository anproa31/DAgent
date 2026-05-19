import re
from langgraph.types import interrupt
from agents.state import AgentState
from agents.planner import create_observation
from utils.agent_logger import get_logger
from utils.llm_client import get_async_client, chat_complete
from utils.prompts import SQL_AGENT_SYSTEM, format_semantic_context_for_prompt

logger = get_logger("sql_agent")


async def sql_agent_node(state: AgentState) -> dict:
    """Generate SQL from the natural-language query, then pause for human review."""
    logger.info("enter query=%r", state["query"][:80])

    client = get_async_client(state.get("base_url", ""), state.get("api_key", ""))
    model = state.get("model", "")
    schema = state.get("schema_info", "No schema available")
    ctx = format_semantic_context_for_prompt(state.get("enhanced_context", ""))

    system_prompt = SQL_AGENT_SYSTEM.format(context=ctx, schema=schema)

    # Check if we have user-edited SQL from a rejection
    user_edited_sql = state.get("sql_draft", "")
    rejection_reason = state.get("sql_rejection_reason", "")

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": state["query"]},
    ]

    # Retry logic: if rejected previously, include rejection reason and user's edited SQL
    if rejection_reason and user_edited_sql:
        # User provided edited SQL with rejection - use it as base for regeneration
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
        # Rejected but no user-edited SQL - just regenerate from scratch
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
        raw = await chat_complete(client, model, messages, temperature=0.1, log_tag="sql_agent")
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

    # Parse SQL and EXPLANATION
    sql_draft = ""
    sql_explanation = ""

    sql_match = re.search(r"SQL:\s*(.+?)(?=EXPLANATION:|$)", raw, re.DOTALL | re.IGNORECASE)
    exp_match = re.search(r"EXPLANATION:\s*(.+)", raw, re.DOTALL | re.IGNORECASE)

    if sql_match:
        sql_draft = sql_match.group(1).strip().strip("`").strip()
        # Remove markdown sql fences if present
        sql_draft = re.sub(r"^```sql\s*", "", sql_draft, flags=re.IGNORECASE)
        sql_draft = re.sub(r"```$", "", sql_draft).strip()
    else:
        # Fallback: try to find a SELECT statement
        sel_match = re.search(r"(SELECT .+)", raw, re.DOTALL | re.IGNORECASE)
        sql_draft = sel_match.group(1).strip() if sel_match else raw.strip()

    if exp_match:
        sql_explanation = exp_match.group(1).strip()

    logger.info("generated SQL:\n%s", sql_draft)

    # ── Human-in-the-Loop: pause and send SQL to the user for review ──
    # interrupt() suspends graph execution until resumed via Command(resume=...)
    approval = interrupt(
        {
            "type": "sql_review",
            "sql": sql_draft,
            "explanation": sql_explanation,
            "query": state["query"],
        }
    )

    # Execution resumes here after user approves/rejects
    approved = approval.get("approved", False)
    edited_sql = approval.get("sql", sql_draft)  # user may edit SQL
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
        # Return to planner for re-plan
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
    """After SQL agent: if approved go to code_executor, else back to planner."""
    if state.get("sql_approved"):
        return "code_executor"
    # Not approved or error → back to planner for re-plan
    return "planner"
