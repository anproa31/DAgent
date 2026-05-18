"""Debug node: log viz_agent outputs and sandbox /var responses before final_report."""
from agents.state import AgentState
from services.code_runner import get_variable


async def viz_debug_node(state: AgentState) -> dict:
    """Validate viz_agent outputs by checking each variable in the sandbox.

    Logs:
    - viz_var_names populated by viz_agent
    - Each variable's /var response (type, data size)
    - Session ID used for retrieval
    """
    session_id = state.get("session_id", state.get("run_id", "default"))
    viz_vars = state.get("viz_var_names", [])

    print(f"[viz_debug] session_id={session_id}")
    print(f"[viz_debug] viz_var_names={viz_vars}")

    debug_info = []
    for var_name in viz_vars:
        result = await get_variable(session_id, var_name)
        if result is None:
            debug_info.append(f"{var_name}: /var returned None")
        elif "error" in result:
            debug_info.append(f"{var_name}: /var error={result['error']}")
        elif "result" in result:
            for item in result["result"]:
                var_type = item.get("type", "unknown")
                data = item.get("data", "")
                data_len = len(data) if data else 0
                debug_info.append(f"{var_name}: type={var_type}, data_len={data_len}")
        else:
            debug_info.append(f"{var_name}: unexpected response keys={result.keys()}")

    if not viz_vars:
        debug_info.append("viz_var_names is empty - viz_agent may have failed to capture figure names")

    print("[viz_debug] results:")
    for line in debug_info:
        print(f"  {line}")

    return {
        "current_agent": "viz_debug",
        "agent_steps": state.get("agent_steps", []) + ["viz_debug"],
    }
