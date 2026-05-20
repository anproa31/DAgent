"""Dispatch tool calls by name."""
from __future__ import annotations

from typing import Any, List

from tools.registry import get_tool
from tools.schemas import ToolResult


async def run_tool(session_id: str, name: str, **kwargs: Any) -> ToolResult:
    tool = get_tool(name)
    if tool is None:
        return ToolResult(
            success=False,
            error=f"Unknown tool: {name}",
            chunks=[{"output_type": "text", "content": f"Unknown tool: {name}"}],
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

    if name == "execute_sql" and "result_variable" not in call_kwargs:
        call_kwargs["result_variable"] = "df_result"

    return await tool.handler(**call_kwargs)


def list_tool_names() -> List[str]:
    from tools.registry import SANDBOX_TOOLS

    return list(SANDBOX_TOOLS.keys())
