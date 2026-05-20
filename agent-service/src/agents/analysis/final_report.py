from agents.shared.state import AgentState
from infrastructure.sandbox.code_runner import get_variable_results
from utils.agent_logger import get_logger
from utils.llm_client import get_async_client, chat_complete
from utils.prompts import RETRIEVAL_RESPONSE_SYSTEM

logger = get_logger("final_report")


async def final_report_node(state: AgentState) -> dict:
    intent = state.get("intent", "ANALYTICAL")
    logger.info("enter intent=%s", intent)

    session_id = state.get("session_id", state.get("run_id", "default"))
    content = []

    if state.get("error") and not state.get("insights"):
        content.append({"type": "markdown", "content": f"**Error:** {state['error']}"})
        return {"report_content": content, "done": True, "current_agent": "final_report"}

    if intent == "RETRIEVAL":
        content = await _build_retrieval_report(state, session_id)
    else:
        content = await _build_analytical_report(state, session_id)

    logger.info("exit sections=%d", len(content))
    return {
        "report_content": content,
        "done": True,
        "current_agent": "final_report",
        "agent_steps": state.get("agent_steps", []) + ["final_report"],
    }


async def _build_retrieval_report(state: AgentState, session_id: str) -> list:
    content = []

    sql = state.get("sql_draft", "")
    if sql:
        content.append({"type": "markdown", "content": f"```sql\n{sql}\n```"})

    result_vars = state.get("result_var_names", [])
    if result_vars:
        data_content = await get_variable_results(session_id, result_vars)
        content.extend(data_content)

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
                client,
                model,
                [{"role": "system", "content": prompt}, {"role": "user", "content": state.get("query", "")}],
                temperature=0.1,
                log_tag="final_report",
            )
            content.append({"type": "markdown", "content": response_text})
        except Exception as exc:
            logger.warning("retrieval response LLM failed: %s", exc)

    return content


async def _build_analytical_report(state: AgentState, session_id: str) -> list:
    content = []

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

    result_vars = state.get("result_var_names", [])
    if result_vars:
        data_content = await get_variable_results(session_id, result_vars)
        content.extend(data_content)

    eda = state.get("eda_summary", "")
    if eda:
        content.append({"type": "markdown", "content": f"## Exploratory Analysis\n{eda}"})

    insights = state.get("insights", "")
    if insights:
        content.append({"type": "markdown", "content": f"## Business Insights\n{insights}"})

    viz_vars = state.get("viz_var_names", [])
    if viz_vars:
        viz_content = await get_variable_results(session_id, viz_vars)
        if viz_content:
            content.append({"type": "markdown", "content": "## Visualizations"})
            content.extend(viz_content)

    return content
