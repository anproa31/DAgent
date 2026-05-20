"""Structured observations passed from worker agents back to the planner."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from tools.schemas import ToolResult


def create_observation(
    agent_name: str,
    status: str,
    summary: str,
    artifacts: Dict[str, Any],
    error: Optional[str] = None,
    chunks: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Create a structured observation for the planner."""
    observation: Dict[str, Any] = {
        "agent": agent_name,
        "status": status,
        "summary": summary,
        "artifacts": artifacts,
        "error": error,
    }
    if chunks is not None:
        observation["chunks"] = chunks
        artifacts.setdefault("chunks", chunks)
    return observation


def observation_from_tool_result(
    agent_name: str,
    tool_name: str,
    result: ToolResult,
    summary: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a planner observation from a sandbox tool result."""
    status = "success" if result.success else "error"
    artifacts = result.to_observation_artifacts()
    artifacts["tool"] = tool_name
    return create_observation(
        agent_name=agent_name,
        status=status,
        summary=summary or _default_summary(tool_name, result),
        artifacts=artifacts,
        error=result.error,
        chunks=result.chunks,
    )


def _default_summary(tool_name: str, result: ToolResult) -> str:
    if not result.success:
        return f"{tool_name} failed: {result.error or 'unknown error'}"
    if tool_name == "execute_sql":
        rows = result.data.get("rows", 0)
        cols = len(result.data.get("columns", []))
        return f"Executed SQL: {rows} rows, {cols} columns"
    if tool_name == "execute_python":
        return "Python code executed successfully"
    if tool_name == "get_variable":
        return f"Retrieved variable '{result.data.get('variable_name', '')}'"
    return f"{tool_name} completed"
