"""Registry of sandbox-backed analytics tools."""
from __future__ import annotations

import json
from typing import Dict, List, Optional

from tools.handlers import (
    handle_discover_web_data,
    handle_execute_python,
    handle_execute_sql,
    handle_fetch_web_data,
    handle_get_variable,
    handle_get_variables,
    handle_propose_web_data,
    handle_register_web_data,
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
    "discover_web_data": ToolDefinition(
        name="discover_web_data",
        description="One-shot search + register (prefer propose/register with HITL in agent flow).",
        parameters={
            "query": _param("query", "string", "Natural language data need", required=False),
            "url": _param("url", "string", "Optional direct HTTPS file URL", required=False),
            "name": _param("name", "string", "Optional datasource name", required=False),
            "model": _param("model", "string", "LLM model for ranking", required=False),
            "base_url": _param("base_url", "string", "LLM API base URL", required=False),
            "api_key": _param("api_key", "string", "LLM API key", required=False),
            "max_results": ToolParameter(
                name="max_results",
                type="integer",
                description="Maximum datasets to fetch",
                required=False,
                default=3,
            ),
        },
        handler=handle_discover_web_data,
    ),
    "propose_web_data": ToolDefinition(
        name="propose_web_data",
        description=(
            "Search trusted public sources and propose downloadable dataset URLs. "
            "Does not register until the user approves."
        ),
        parameters={
            "query": _param("query", "string", "Natural language data need", required=False),
            "url": _param("url", "string", "Optional direct HTTPS file URL", required=False),
            "model": _param("model", "string", "LLM model for ranking", required=False),
            "base_url": _param("base_url", "string", "LLM API base URL", required=False),
            "api_key": _param("api_key", "string", "LLM API key", required=False),
            "max_results": ToolParameter(
                name="max_results",
                type="integer",
                description="Maximum URLs to propose",
                required=False,
                default=3,
            ),
        },
        handler=handle_propose_web_data,
    ),
    "register_web_data": ToolDefinition(
        name="register_web_data",
        description="Download and register user-approved dataset URLs as datasources.",
        parameters={
            "urls": _param("urls", "array", "Approved HTTPS dataset URLs"),
            "name": _param("name", "string", "Optional datasource name prefix", required=False),
            "query": _param("query", "string", "Original user query context", required=False),
        },
        handler=handle_register_web_data,
    ),
    "fetch_web_data": ToolDefinition(
        name="fetch_web_data",
        description=(
            "Download a dataset from a trusted HTTPS URL and register it as a datasource. "
            "Use when you already have a direct link to a data file."
        ),
        parameters={
            "url": _param("url", "string", "Direct HTTPS URL to the data file"),
            "name": _param("name", "string", "Optional datasource display name", required=False),
        },
        handler=handle_fetch_web_data,
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
