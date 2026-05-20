"""Registry of sandbox-backed analytics tools."""
from __future__ import annotations

import json
from typing import Dict, List, Optional

from tools.handlers import (
    handle_execute_python,
    handle_execute_sql,
    handle_get_variable,
    handle_get_variables,
    handle_rollback,
)
from tools.schemas import ToolDefinition, ToolParameter


def _param(name: str, type_: str, description: str, required: bool = True) -> ToolParameter:
    return ToolParameter(name=name, type=type_, description=description, required=required)


SANDBOX_TOOLS: Dict[str, ToolDefinition] = {
    "execute_python": ToolDefinition(
        name="execute_python",
        description=(
            "Run pandas/numpy/matplotlib Python code in a stateful sandbox session. "
            "Variables persist across calls within the same session_id."
        ),
        parameters={
            "code": _param("code", "string", "Python source code to execute"),
        },
        handler=handle_execute_python,
    ),
    "execute_sql": ToolDefinition(
        name="execute_sql",
        description=(
            "Execute SQL against the shared DuckDB engine. "
            "Materialises the result as a pandas DataFrame in the session."
        ),
        parameters={
            "sql": _param("sql", "string", "SQL query to run"),
            "result_variable": ToolParameter(
                name="result_variable",
                type="string",
                description="Session variable name for the result DataFrame",
                required=False,
                default="df_result",
            ),
        },
        handler=handle_execute_sql,
    ),
    "get_variable": ToolDefinition(
        name="get_variable",
        description="Retrieve a session variable (table, image, or scalar) by name.",
        parameters={
            "name": _param("name", "string", "Variable name or formatted expression"),
        },
        handler=handle_get_variable,
    ),
    "get_variables": ToolDefinition(
        name="get_variables",
        description="Retrieve multiple session variables (e.g. chart figures).",
        parameters={
            "names": _param("names", "array", "List of variable names"),
        },
        handler=handle_get_variables,
    ),
    "rollback": ToolDefinition(
        name="rollback",
        description="Restore session variables to the state before the last Python execution.",
        parameters={},
        handler=handle_rollback,
    ),
}


def get_tool(name: str) -> Optional[ToolDefinition]:
    return SANDBOX_TOOLS.get(name)


def list_tools() -> List[ToolDefinition]:
    return list(SANDBOX_TOOLS.values())


def format_tools_for_prompt() -> str:
    """Render tool catalog for LLM system prompts."""
    lines = ["## Available Sandbox Tools", ""]
    for tool in list_tools():
        schema = tool.parameter_schema()
        lines.append(f"### `{tool.name}`")
        lines.append(tool.description)
        lines.append(f"Parameters: `{json.dumps(schema, ensure_ascii=False)}`")
        lines.append("")
    return "\n".join(lines).strip()
