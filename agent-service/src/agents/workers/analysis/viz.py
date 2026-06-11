import re

from agents.shared.act import invoke_tool, observe_from_tool
from agents.shared.observations import create_observation
from agents.shared.state import AgentState
from agents.shared.worker_context import build_worker_user_message
from utils.agent_logger import get_logger
from utils.llm_client import get_async_client, chat_complete
from utils.prompts import VIZ_AGENT_SYSTEM, format_semantic_context_for_prompt, format_language_rule

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
        language_rule=format_language_rule(state.get("language", "en")),
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

    logger.info("generated code (%d chars)", len(viz_code))

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

    # Capture every open matplotlib figure deterministically — do NOT rely on the
    # LLM binding figures to ``fig``-named variables (it frequently does not).
    # Drop cosmetic-only duplicates: figures whose title + axis labels are
    # identical convey the same information, so keep only the first.
    capture_var = "_viz_figures"
    code_to_run = (
        f"{viz_code}\n\n"
        "import matplotlib.pyplot as plt\n"
        "def _viz_signature(_f):\n"
        "    _st = getattr(_f, '_suptitle', None)\n"
        "    _parts = [_st.get_text() if _st is not None else '']\n"
        "    for _ax in _f.get_axes():\n"
        "        _parts += [_ax.get_title(), _ax.get_xlabel(), _ax.get_ylabel()]\n"
        "    return '|'.join(_parts)\n"
        "_viz_seen = set()\n"
        f"{capture_var} = []\n"
        "for _n in plt.get_fignums():\n"
        "    _fig = plt.figure(_n)\n"
        "    _sig = _viz_signature(_fig)\n"
        "    if _sig in _viz_seen:\n"
        "        continue\n"
        "    _viz_seen.add(_sig)\n"
        f"    {capture_var}.append(_fig)\n"
    )

    exec_result = await invoke_tool(
        state,
        "execute_python",
        agent_role="viz",
        code=code_to_run,
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
        summary="Generated visualization(s)",
        extra_artifacts={"viz_code": viz_code, "viz_var_names": [capture_var]},
    )

    return {
        "current_agent": "viz",
        "viz_code": viz_code,
        "viz_var_names": [capture_var],
        "agent_steps": state.get("agent_steps", []) + ["viz"],
        **observe_patch,
    }
