"""Executes approved SQL via the sandbox DuckDB engine."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from agents.shared.data_discovery import extract_data_discovery_error
from agents.shared.observations import create_observation
from agents.shared.state import AgentState
from infrastructure.sandbox.code_runner import execute_sql, get_variable
from utils.agent_logger import get_logger

logger = get_logger("code_executor")


async def code_executor_node(state: AgentState) -> dict:
    sql = state.get("sql_draft", "")
    session_id = state.get("session_id", state.get("run_id", "default"))

    logger.info("enter session=%s sql=%r", session_id, sql[:200] if sql else "")

    result = await execute_sql(sql, session_id, result_variable="df_result")
    if "code_error" in result or "error" in result:
        err = result.get("code_error") or result.get("error")
        logger.error("SQL execution failed: %s", err)

        data_discovery_error = extract_data_discovery_error(err)

        obs = create_observation(
            agent_name="code_executor",
            status="error",
            summary=f"SQL execution failed: {err}",
            artifacts={
                "data_summary": f"Error: {err}",
                "result_var_names": [],
                "data_discovery_error": data_discovery_error,
            },
            error=err,
        )
        return {
            "current_agent": "code_executor",
            "data_summary": f"Execution error: {err}",
            "result_var_names": [],
            "agent_steps": state.get("agent_steps", []) + ["code_executor"],
            "error": f"Code execution error: {err}",
            "last_observation": obs,
        }

    columns: List[str] = result.get("columns", [])
    rows = int(result.get("rows", 0))
    preview: List[Dict[str, Any]] = result.get("preview", [])

    data_summary = _build_data_summary(columns, rows, preview)
    logger.info("exit rows=%d columns=%d", rows, len(columns))

    obs = create_observation(
        agent_name="code_executor",
        status="success",
        summary=f"Executed SQL: {rows} rows, {len(columns)} columns",
        artifacts={
            "data_summary": data_summary,
            "result_var_names": ["df_result"],
            "sql_draft": sql,
        },
        error=None,
    )

    return {
        "current_agent": "code_executor",
        "data_summary": data_summary,
        "result_var_names": ["df_result"],
        "agent_steps": state.get("agent_steps", []) + ["code_executor"],
        "last_observation": obs,
    }


def _build_data_summary(columns: List[str], row_count: int, preview: List[Dict[str, Any]]) -> str:
    if not columns:
        return "No data returned"
    if row_count == 0:
        return f"Columns: {columns}\nRow count: 0"
    header = " | ".join(columns)
    preview_lines = [
        " | ".join(str(row.get(col, "")) for col in columns) for row in preview[:5]
    ]
    return (
        f"Columns: {columns}\n"
        f"Row count: {row_count}\n"
        f"Preview ({min(5, row_count)} rows):\n"
        f"{header}\n" + "\n".join(preview_lines)
    )
