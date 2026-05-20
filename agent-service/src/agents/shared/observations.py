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
    next_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a structured observation for the planner.

    Schema (solution.md §1 Fix 1):
      agent       — worker that produced the observation
      status      — success | error | rejected | skipped | partial
      summary     — short (<=~100 char) signal the planner reads
      artifacts   — full data payload (planner does NOT read this directly)
      error       — populated when status == error
      next_hint   — optional steer for the planner's next action
    """
    observation: Dict[str, Any] = {
        "agent": agent_name,
        "status": status,
        "summary": _truncate_summary(summary),
        "artifacts": artifacts,
        "error": error,
        "next_hint": next_hint,
    }
    if chunks is not None:
        observation["chunks"] = chunks
        artifacts.setdefault("chunks", chunks)
    return observation


_SUMMARY_MAX_CHARS = 200


def _truncate_summary(summary: Optional[str]) -> str:
    text = (summary or "").strip()
    if len(text) <= _SUMMARY_MAX_CHARS:
        return text
    return text[: _SUMMARY_MAX_CHARS - 1].rstrip() + "…"


def observation_from_tool_result(
    agent_name: str,
    tool_name: str,
    result: ToolResult,
    summary: Optional[str] = None,
    next_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a planner observation from a sandbox tool result."""
    status = "success" if result.success else "error"
    artifacts = result.to_observation_artifacts()
    artifacts["tool"] = tool_name
    if next_hint is None and not result.success:
        next_hint = f"{tool_name} failed — fix the input or try an alternate action."
    return create_observation(
        agent_name=agent_name,
        status=status,
        summary=summary or _default_summary(tool_name, result),
        artifacts=artifacts,
        error=result.error,
        chunks=result.chunks,
        next_hint=next_hint,
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
    if tool_name in ("discover_web_data", "fetch_web_data", "register_web_data"):
        views = result.data.get("view_names") or []
        return f"Web discovery registered {len(views)} view(s)"
    if tool_name == "propose_web_data":
        urls = result.data.get("selected_urls") or []
        return f"Proposed {len(urls)} web dataset URL(s) for approval"
    return f"{tool_name} completed"
