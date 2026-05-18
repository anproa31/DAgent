from agents.state import AgentState
from services.code_runner import get_variable_results


async def final_report_node(state: AgentState) -> dict:
    """Compile all agent outputs into a structured report content list."""
    print("[final_report] compiling report")

    session_id = state.get("session_id", state.get("run_id", "default"))
    content = []

    # Error shortcut
    if state.get("error") and not state.get("insights"):
        content.append({"type": "markdown", "content": f"**Error:** {state['error']}"})
        return {"report_content": content, "done": True, "current_agent": "final_report"}

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

    return {
        "report_content": content,
        "done": True,
        "current_agent": "final_report",
        "agent_steps": state.get("agent_steps", []) + ["final_report"],
    }
