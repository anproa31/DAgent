from agents.shared.state import AgentState
from infrastructure.sandbox.code_runner import get_variable_results
from orchestration.streaming import make_delta_emitter
from utils.agent_logger import get_logger
from utils.llm_client import get_async_client, chat_complete
from utils.prompts import RETRIEVAL_RESPONSE_SYSTEM


def _python_code_block(state: AgentState) -> dict | None:
    """Fenced Python block for the final report (mirrors how SQL is shown)."""
    code = (state.get("python_code") or "").strip()
    if not code:
        return None
    return {"type": "markdown", "content": f"## Analysis Code\n```python\n{code}\n```"}

logger = get_logger("final_report")


def _has_reportable_content(state: AgentState) -> bool:
    """True when we can build a substantive report despite an upstream worker error."""
    if state.get("insights") or state.get("eda_summary"):
        return True
    if state.get("result_var_names") or state.get("viz_var_names"):
        return True
    if state.get("sql_draft") or state.get("python_code"):
        return True
    data_summary = state.get("data_summary", "")
    return bool(data_summary and data_summary != "No data returned")


async def final_report_node(state: AgentState) -> dict:
    intent = state.get("intent", "ANALYTICAL")
    logger.info("enter intent=%s", intent)

    session_id = state.get("session_id", state.get("run_id", "default"))
    content = []

    if state.get("error") and not _has_reportable_content(state):
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

    python_block = _python_code_block(state)
    if python_block:
        content.append(python_block)

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
                on_delta=make_delta_emitter(state.get("run_id", ""), "final_report"),
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

    python_block = _python_code_block(state)
    if python_block:
        content.append(python_block)

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
