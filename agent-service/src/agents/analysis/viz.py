import re

from agents.shared.observations import create_observation, observation_from_tool_result
from agents.shared.state import AgentState
from tools.executor import run_tool
from utils.agent_logger import get_logger
from utils.llm_client import get_async_client, chat_complete
from utils.prompts import VIZ_AGENT_SYSTEM, format_semantic_context_for_prompt

logger = get_logger("viz_agent")


async def viz_agent_node(state: AgentState) -> dict:
    logger.info("enter")

    client = get_async_client(state.get("base_url", ""), state.get("api_key", ""))
    model = state.get("model", "")

    ctx = format_semantic_context_for_prompt(state.get("enhanced_context", ""))

    system_prompt = VIZ_AGENT_SYSTEM.format(
        context=ctx,
        schema=state.get("schema_info", ""),
        query=state.get("query", ""),
        insights=state.get("insights", ""),
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": (
                f"Data summary: {state.get('data_summary', '')}\n\n"
                f"Create visualizations for: {state['query']}"
            ),
        },
    ]

    try:
        raw = await chat_complete(client, model, messages, temperature=0.3, log_tag="viz_agent")
    except Exception as e:
        logger.error("LLM error: %s", e)
        obs = create_observation(
            agent_name="viz",
            status="error",
            summary=f"Viz code generation failed: {e}",
            artifacts={"viz_code": "", "viz_var_names": []},
            error=str(e),
        )
        return {
            "current_agent": "viz",
            "viz_code": "",
            "viz_var_names": [],
            "agent_steps": state.get("agent_steps", []) + ["viz"],
            "last_observation": obs,
        }

    code_match = re.search(r"<python>(.*?)</python>", raw, re.DOTALL)
    if code_match:
        viz_code = code_match.group(1).strip()
    else:
        viz_code = re.sub(r"^```python\s*|\s*```$", "", raw.strip(), flags=re.MULTILINE)
        viz_code = viz_code.strip()

    var_names = re.findall(r"\b(?!figsize\b)(fig\w*|figure\w*)\s*(?:,|\s*=)", viz_code)
    var_names = list(dict.fromkeys(var_names))

    logger.info("generated code (%d chars), vars=%s", len(viz_code), var_names)

    session_id = state.get("session_id", state.get("run_id", "default"))
    if not viz_code:
        obs = create_observation(
            agent_name="viz",
            status="success",
            summary="No visualization code generated",
            artifacts={"viz_code": "", "viz_var_names": []},
        )
        return {
            "current_agent": "viz",
            "viz_code": "",
            "viz_var_names": [],
            "agent_steps": state.get("agent_steps", []) + ["viz"],
            "last_observation": obs,
        }

    exec_result = await run_tool(session_id, "execute_python", code=viz_code)
    if not exec_result.success:
        err = exec_result.error or "Viz execution failed"
        logger.error("visualization code error: %s", err)
        obs = observation_from_tool_result("viz", "execute_python", exec_result)
        obs["artifacts"]["viz_code"] = viz_code
        obs["artifacts"]["viz_var_names"] = []
        return {
            "current_agent": "viz",
            "viz_code": viz_code,
            "viz_var_names": [],
            "agent_steps": state.get("agent_steps", []) + ["viz"],
            "last_observation": obs,
        }

    obs = observation_from_tool_result("viz", "execute_python", exec_result)
    obs["summary"] = f"Generated {len(var_names)} chart(s)"
    obs["artifacts"]["viz_code"] = viz_code
    obs["artifacts"]["viz_var_names"] = var_names

    return {
        "current_agent": "viz",
        "viz_code": viz_code,
        "viz_var_names": var_names,
        "agent_steps": state.get("agent_steps", []) + ["viz"],
        "last_observation": obs,
    }
