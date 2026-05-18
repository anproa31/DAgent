from agents.state import AgentState
from utils.llm_client import get_async_client, chat_complete
from utils.prompts import EDA_AGENT_SYSTEM


async def eda_agent_node(state: AgentState) -> dict:
    """Perform exploratory data analysis on the retrieved data."""
    print("[eda_agent] running EDA")

    data_summary = state.get("data_summary", "No data available")
    schema = state.get("schema_info", "")

    client = get_async_client(state.get("base_url", ""), state.get("api_key", ""))
    model = state.get("model", "")

    system_prompt = EDA_AGENT_SYSTEM.format(
        schema=schema,
        data_summary=data_summary,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Perform EDA for this query: {state['query']}"},
    ]

    try:
        eda_summary = await chat_complete(client, model, messages, temperature=0.3)
    except Exception as e:
        eda_summary = f"EDA analysis unavailable: {e}"

    return {
        "current_agent": "eda",
        "eda_summary": eda_summary,
        "agent_steps": state.get("agent_steps", []) + ["eda"],
    }


def route_after_eda(state: AgentState) -> str:
    pipeline = state.get("pipeline", [])
    if "insight" in pipeline:
        return "insight"
    if "viz" in pipeline:
        return "viz"
    return "final_report"
