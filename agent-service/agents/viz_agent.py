import re
from agents.state import AgentState
from utils.llm_client import get_async_client, chat_complete
from utils.prompts import VIZ_AGENT_SYSTEM, format_semantic_context_for_prompt
from services.code_runner import execute_code, get_variable_results


async def viz_agent_node(state: AgentState) -> dict:
    """Generate visualization code, execute it, and capture chart outputs."""
    print("[viz_agent] generating visualizations")

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
        raw = await chat_complete(client, model, messages, temperature=0.3)
    except Exception as e:
        return {
            "current_agent": "viz",
            "viz_code": "",
            "viz_var_names": [],
            "agent_steps": state.get("agent_steps", []) + ["viz"],
        }

    # Extract code from <python>...</python> tags
    code_match = re.search(r"<python>(.*?)</python>", raw, re.DOTALL)
    viz_code = code_match.group(1).strip() if code_match else raw.strip()

    # Find figure variable names (fig1, fig2, fig, figure, etc.)
    var_names = re.findall(r"\b(fig\w*|figure\w*)\s*=", viz_code)
    var_names = list(dict.fromkeys(var_names))  # deduplicate while preserving order

    # Execute visualization code in sandbox
    session_id = state.get("session_id", state.get("run_id", "default"))
    if viz_code:
        exec_result = await execute_code(viz_code, session_id)
        if "code_error" in exec_result or "error" in exec_result:
            err = exec_result.get("code_error") or exec_result.get("error")
            print(f"[viz_agent] visualization code error: {err}")
            var_names = []

    return {
        "current_agent": "viz",
        "viz_code": viz_code,
        "viz_var_names": var_names,
        "agent_steps": state.get("agent_steps", []) + ["viz"],
    }
