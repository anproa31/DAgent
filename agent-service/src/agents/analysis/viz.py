import re

from agents.shared.observations import create_observation
from agents.shared.state import AgentState
from infrastructure.sandbox.code_runner import execute_code, get_variable_results
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
    status = "success"
    exec_result = {}
    if viz_code:
        exec_result = await execute_code(viz_code, session_id)
        if "code_error" in exec_result or "error" in exec_result:
            err = exec_result.get("code_error") or exec_result.get("error")
            logger.error("visualization code error: %s", err)
            var_names = []
            status = "error"

    obs = create_observation(
        agent_name="viz",
        status=status,
        summary=f"Generated {len(var_names)} chart(s)" if status == "success" else "Viz execution failed",
        artifacts={"viz_code": viz_code, "viz_var_names": var_names},
        error=None if status == "success" else exec_result.get("code_error") if viz_code else None,
    )

    return {
        "current_agent": "viz",
        "viz_code": viz_code,
        "viz_var_names": var_names,
        "agent_steps": state.get("agent_steps", []) + ["viz"],
        "last_observation": obs,
    }
