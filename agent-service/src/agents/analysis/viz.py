import re

from agents.shared.act import invoke_tool, observe_from_tool
from agents.shared.observations import create_observation
from agents.shared.state import AgentState
from agents.shared.worker_context import build_worker_user_message
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
    scoped_task = build_worker_user_message(state, "viz")
    data_summary = state.get("data_summary", "")
    user_content = scoped_task
    if data_summary:
        user_content = f"{scoped_task}\n\nAvailable data summary:\n{data_summary}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
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

    exec_result = await invoke_tool(
        state,
        "execute_python",
        agent_role="viz",
        code=viz_code,
    )
    if not exec_result.success:
        err = exec_result.error or "Viz execution failed"
        logger.error("visualization code error: %s", err)
        observe_patch = observe_from_tool(
            state,
            agent_role="viz",
            tool_name="execute_python",
            result=exec_result,
            extra_artifacts={"viz_code": viz_code, "viz_var_names": []},
        )
        return {
            "current_agent": "viz",
            "viz_code": viz_code,
            "viz_var_names": [],
            "agent_steps": state.get("agent_steps", []) + ["viz"],
            **observe_patch,
        }

    observe_patch = observe_from_tool(
        state,
        agent_role="viz",
        tool_name="execute_python",
        result=exec_result,
        summary=f"Generated {len(var_names)} chart(s)",
        extra_artifacts={"viz_code": viz_code, "viz_var_names": var_names},
    )

    return {
        "current_agent": "viz",
        "viz_code": viz_code,
        "viz_var_names": var_names,
        "agent_steps": state.get("agent_steps", []) + ["viz"],
        **observe_patch,
    }
