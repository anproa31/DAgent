from agents.state import AgentState
from services.code_runner import get_variable_results
from utils.llm_client import get_async_client, chat_complete
from utils.prompts import RETRIEVAL_RESPONSE_SYSTEM


async def final_report_node(state: AgentState) -> dict:
    """Compile all agent outputs into a structured report content list."""
    intent = state.get("intent", "ANALYTICAL")
    print(f"[final_report] compiling report (intent={intent})")

    session_id = state.get("session_id", state.get("run_id", "default"))
    content = []

    # Error shortcut
    if state.get("error") and not state.get("insights"):
        content.append({"type": "markdown", "content": f"**Error:** {state['error']}"})
        return {"report_content": content, "done": True, "current_agent": "final_report"}

    if intent == "RETRIEVAL":
        content = await _build_retrieval_report(state, session_id)
    else:
        content = await _build_analytical_report(state, session_id)

    return {
        "report_content": content,
        "done": True,
        "current_agent": "final_report",
        "agent_steps": state.get("agent_steps", []) + ["final_report"],
    }


async def _build_retrieval_report(state: AgentState, session_id: str) -> list:
    """Lightweight report: just the data, no insights or EDA."""
    content = []

    # SQL section (collapsed/minimal)
    sql = state.get("sql_draft", "")
    if sql:
        content.append(
            {
                "type": "markdown",
                "content": f"```sql\n{sql}\n```",
            }
        )

    # Data tables — the main deliverable for retrieval queries
    result_vars = state.get("result_var_names", [])
    if result_vars:
        data_content = await get_variable_results(session_id, result_vars)
        content.extend(data_content)

    # Generate a brief natural-language response for the data
    data_summary = state.get("data_summary", "")
    if data_summary and data_summary != "No data returned":
        client = get_async_client(state.get("base_url", ""), state.get("api_key", ""))
        model = state.get("model", "")
        prompt = RETRIEVAL_RESPONSE_SYSTEM.format(
            query=state.get("query", ""),
            data_summary=data_summary,
        )
        try:
            response_text = await chat_complete(
                client, model,
                [{"role": "system", "content": prompt}, {"role": "user", "content": state.get("query", "")}],
                temperature=0.1,
            )
            content.append({"type": "markdown", "content": response_text})
        except Exception:
            pass

    return content


async def _build_analytical_report(state: AgentState, session_id: str) -> list:
    """Full analytical report with EDA, insights, and visualizations."""
    content = []

    # SQL section
    sql = state.get("sql_draft", "")
    if sql:
        content.append(
            {
                "type": "markdown",
                "content": (
                    f"## Query\n```sql\n{sql}\n```\n"
                    + (f"_{state.get('sql_explanation', '')}_" if state.get("sql_explanation") else "")
                ),
            }
        )

    # Data tables from code executor
    result_vars = state.get("result_var_names", [])
    if result_vars:
        data_content = await get_variable_results(session_id, result_vars)
        content.extend(data_content)

    # EDA summary
    eda = state.get("eda_summary", "")
    if eda:
        content.append({"type": "markdown", "content": f"## Exploratory Analysis\n{eda}"})

    # Business insights
    insights = state.get("insights", "")
    if insights:
        content.append({"type": "markdown", "content": f"## Business Insights\n{insights}"})

    # Visualizations
    viz_vars = state.get("viz_var_names", [])
    if viz_vars:
        viz_content = await get_variable_results(session_id, viz_vars)
        if viz_content:
            content.append({"type": "markdown", "content": "## Visualizations"})
            content.extend(viz_content)

    return content
