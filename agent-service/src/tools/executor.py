"""Tool pipeline: guardrail gate → dispatch → exec → result."""
from __future__ import annotations

from typing import Any, List, Optional

from agents.shared.guardrails import gate_tool_call
from tools.registry import get_tool
from tools.schemas import ToolResult


async def run_tool(
    session_id: str,
    tool_name: str,
    *,
    agent_role: str = "",
    state: Optional[dict] = None,
    **kwargs: Any,
) -> ToolResult:
    # ``tool_name`` (not ``name``) so a tool whose own parameter is called
    # ``name`` (e.g. get_variable) can be passed via kwargs
    # without colliding with this positional argument.
    if state is not None:
        gate = gate_tool_call(state, tool_name, agent_role=agent_role)
        if not gate.allowed:
            return ToolResult(
                success=False,
                error=gate.reason,
                chunks=[{"output_type": "text", "content": gate.reason}],
            )

    tool = get_tool(tool_name)
    if tool is None:
        return ToolResult(
            success=False,
            error=f"Unknown tool: {tool_name}",
            chunks=[{"output_type": "text", "content": f"Unknown tool: {tool_name}"}],
        )

    missing = [
        param.name
        for param in tool.parameters.values()
        if param.required and kwargs.get(param.name) in (None, "")
    ]
    if missing:
        msg = f"Missing required parameters: {', '.join(missing)}"
        return ToolResult(
            success=False,
            error=msg,
            chunks=[{"output_type": "text", "content": msg}],
        )

    call_kwargs = {"session_id": session_id}
    for param in tool.parameters.values():
        if param.name in kwargs and kwargs[param.name] is not None:
            call_kwargs[param.name] = kwargs[param.name]
        elif param.default is not None:
            call_kwargs[param.name] = param.default

    if tool_name == "execute_sql" and "result_variable" not in call_kwargs:
        call_kwargs["result_variable"] = "df_result"

    return await tool.handler(**call_kwargs)


def list_tool_names() -> List[str]:
    from tools.registry import SANDBOX_TOOLS

    return list(SANDBOX_TOOLS.keys())
