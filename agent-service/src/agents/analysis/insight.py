from agents.shared.observations import create_observation
from agents.shared.state import AgentState
from utils.agent_logger import get_logger
from utils.llm_client import get_async_client, chat_complete
from utils.prompts import INSIGHT_AGENT_SYSTEM, format_semantic_context_for_prompt

logger = get_logger("insight_agent")


async def insight_agent_node(state: AgentState) -> dict:
    logger.info("enter")

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
        insights = await chat_complete(client, model, messages, temperature=0.4, log_tag="insight_agent")
        logger.info("exit success (%d chars)", len(insights))
        obs = create_observation(
            agent_name="insight",
            status="success",
            summary=f"Generated {insights.count('**')} insights",
            artifacts={"insights": insights},
            error=None,
        )
    except Exception as e:
        logger.error("LLM error: %s", e)
        insights = f"Insight generation failed: {e}"
        obs = create_observation(
            agent_name="insight",
            status="error",
            summary=f"Insight generation failed: {e}",
            artifacts={"insights": ""},
            error=str(e),
        )

    return {
        "current_agent": "insight",
        "insights": insights,
        "agent_steps": state.get("agent_steps", []) + ["insight"],
        "last_observation": obs,
    }
