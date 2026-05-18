from agents.state import AgentState
from utils.llm_client import get_async_client, chat_complete
from utils.prompts import INSIGHT_AGENT_SYSTEM, format_semantic_context_for_prompt


async def insight_agent_node(state: AgentState) -> dict:
    """Generate business insights from data and EDA findings."""
    print("[insight_agent] generating insights")

    client = get_async_client(state.get("base_url", ""), state.get("api_key", ""))
    model = state.get("model", "")

    ctx = format_semantic_context_for_prompt(state.get("enhanced_context", ""))

    system_prompt = INSIGHT_AGENT_SYSTEM.format(
        query=state.get("query", ""),
        context=ctx,
        schema=state.get("schema_info", ""),
        data_summary=state.get("data_summary", "No data"),
        eda_summary=state.get("eda_summary", "No EDA performed"),
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": state["query"]},
    ]

    try:
        insights = await chat_complete(client, model, messages, temperature=0.4)
    except Exception as e:
        insights = f"Insight generation failed: {e}"

    return {
        "current_agent": "insight",
        "insights": insights,
        "agent_steps": state.get("agent_steps", []) + ["insight"],
    }


def route_after_insight(state: AgentState) -> str:
    pipeline = state.get("pipeline", [])
    if "viz" in pipeline:
        return "viz"
    return "final_report"
