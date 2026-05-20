from agents.shared.observations import create_observation
from agents.shared.state import AgentState
from utils.agent_logger import get_logger
from utils.llm_client import get_async_client, chat_complete
from utils.prompts import EDA_AGENT_SYSTEM, format_semantic_context_for_prompt

logger = get_logger("eda_agent")


async def eda_agent_node(state: AgentState) -> dict:
    logger.info("enter")

    data_summary = state.get("data_summary", "No data available")
    schema = state.get("schema_info", "")
    ctx = format_semantic_context_for_prompt(state.get("enhanced_context", ""))

    client = get_async_client(state.get("base_url", ""), state.get("api_key", ""))
    model = state.get("model", "")

    system_prompt = EDA_AGENT_SYSTEM.format(
        context=ctx,
        schema=schema,
        data_summary=data_summary,
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Perform EDA for this query: {state['query']}"},
    ]

    try:
        eda_summary = await chat_complete(client, model, messages, temperature=0.3, log_tag="eda_agent")
        logger.info("exit success (%d chars)", len(eda_summary))
        obs = create_observation(
            agent_name="eda",
            status="success",
            summary=f"EDA completed: {eda_summary[:100]}...",
            artifacts={"eda_summary": eda_summary},
            error=None,
        )
    except Exception as e:
        logger.error("LLM error: %s", e)
        eda_summary = f"EDA analysis unavailable: {e}"
        obs = create_observation(
            agent_name="eda",
            status="error",
            summary=f"EDA failed: {e}",
            artifacts={"eda_summary": ""},
            error=str(e),
        )

    return {
        "current_agent": "eda",
        "eda_summary": eda_summary,
        "agent_steps": state.get("agent_steps", []) + ["eda"],
        "last_observation": obs,
    }
