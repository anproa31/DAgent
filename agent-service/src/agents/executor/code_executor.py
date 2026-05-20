"""Executes approved SQL via the sandbox DuckDB engine."""

from __future__ import annotations

from typing import List

from agents.shared.data_discovery import extract_data_discovery_error
from agents.shared.observations import observation_from_tool_result
from agents.shared.state import AgentState
from tools.executor import run_tool
from utils.agent_logger import get_logger
from utils.sql_sanitize import clean_sql_for_execution

logger = get_logger("code_executor")


async def code_executor_node(state: AgentState) -> dict:
    sql = clean_sql_for_execution(state.get("sql_draft", ""))
    session_id = state.get("session_id", state.get("run_id", "default"))

    logger.info("enter session=%s sql=%r", session_id, sql[:200] if sql else "")

    tool_result = await run_tool(session_id, "execute_sql", sql=sql, result_variable="df_result")
    if not tool_result.success:
        err = tool_result.error or "SQL execution failed"
        logger.error("SQL execution failed: %s", err)

        data_discovery_error = extract_data_discovery_error(err)
        obs = observation_from_tool_result("code_executor", "execute_sql", tool_result)
        obs["artifacts"]["data_summary"] = f"Error: {err}"
        obs["artifacts"]["result_var_names"] = []
        obs["artifacts"]["data_discovery_error"] = data_discovery_error

        return {
            "current_agent": "code_executor",
            "data_summary": f"Execution error: {err}",
            "result_var_names": [],
            "agent_steps": state.get("agent_steps", []) + ["code_executor"],
            "error": f"Code execution error: {err}",
            "last_observation": obs,
        }

    data_summary = tool_result.data.get("data_summary", "No data returned")
    rows = int(tool_result.data.get("rows", 0))
    columns: List[str] = tool_result.data.get("columns", [])
    logger.info("exit rows=%d columns=%d", rows, len(columns))

    obs = observation_from_tool_result("code_executor", "execute_sql", tool_result)
    obs["artifacts"]["sql_draft"] = sql

    return {
        "current_agent": "code_executor",
        "data_summary": data_summary,
        "result_var_names": ["df_result"],
        "agent_steps": state.get("agent_steps", []) + ["code_executor"],
        "last_observation": obs,
    }
