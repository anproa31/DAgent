import re
from langgraph.types import interrupt
from agents.state import AgentState
from utils.llm_client import get_async_client, chat_complete
from utils.prompts import SQL_AGENT_SYSTEM, format_semantic_context_for_prompt


async def sql_agent_node(state: AgentState) -> dict:
    """Generate SQL from the natural-language query, then pause for human review."""
    print(f"[sql_agent] generating SQL for: {state['query'][:80]}")

    client = get_async_client(state.get("base_url", ""), state.get("api_key", ""))
    model = state.get("model", "")
    schema = state.get("schema_info", "No schema available")
    ctx = format_semantic_context_for_prompt(state.get("enhanced_context", ""))

    system_prompt = SQL_AGENT_SYSTEM.format(context=ctx, schema=schema)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": state["query"]},
    ]

    # Retry logic: if rejected previously, include rejection reason in messages
    rejection_reason = state.get("sql_rejection_reason", "")
    if rejection_reason and state.get("sql_draft"):
        messages.append({"role": "assistant", "content": f"SQL: {state['sql_draft']}"})
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
        raw = await chat_complete(client, model, messages, temperature=0.1)
    except Exception as e:
        print(f"[sql_agent] LLM error: {e}")
        return {
            "current_agent": "sql",
            "error": f"SQL generation failed: {e}",
            "agent_steps": state.get("agent_steps", []) + ["sql"],
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

    print(f"[sql_agent] generated SQL:\n{sql_draft}")

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

    if not approved:
        # Re-generate with rejection context
        return {
            "current_agent": "sql",
            "sql_draft": edited_sql or sql_draft,
            "sql_explanation": sql_explanation,
            "sql_approved": False,
            "sql_rejection_reason": rejection_reason_new,
            "agent_steps": state.get("agent_steps", []) + ["sql"],
        }

    return {
        "current_agent": "sql",
        "sql_draft": edited_sql,
        "sql_explanation": sql_explanation,
        "sql_approved": True,
        "sql_rejection_reason": "",
        "agent_steps": state.get("agent_steps", []) + ["sql"],
    }


def route_after_sql(state: AgentState) -> str:
    """After SQL agent: if approved go to code_executor, else retry sql."""
    if state.get("sql_approved"):
        return "code_executor"
    if state.get("error"):
        return "final_report"
    # Not approved → loop back to sql_agent to regenerate
    return "sql"
