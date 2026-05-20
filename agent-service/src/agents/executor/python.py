"""Python-first execution path for pandas/numpy/scipy analytics."""

from __future__ import annotations

import json
import re

from agents.shared.data_discovery import extract_data_discovery_error
from agents.shared.observations import create_observation
from agents.shared.state import AgentState
from infrastructure.sandbox.code_runner import execute_code, get_variable
from utils.agent_logger import get_logger
from utils.llm_client import chat_complete, get_async_client
from utils.prompts import PYTHON_AGENT_SYSTEM, format_semantic_context_for_prompt

logger = get_logger("python_agent")


async def python_agent_node(state: AgentState) -> dict:
    logger.info("enter query=%r", state["query"][:80])

    client = get_async_client(state.get("base_url", ""), state.get("api_key", ""))
    model = state.get("model", "")
    schema = state.get("schema_info", "No schema available")
    ctx = format_semantic_context_for_prompt(state.get("enhanced_context", ""))

    messages = [
        {"role": "system", "content": PYTHON_AGENT_SYSTEM.format(context=ctx, schema=schema)},
        {"role": "user", "content": state["query"]},
    ]

    try:
        raw = await chat_complete(client, model, messages, temperature=0.2, log_tag="python_agent")
    except Exception as exc:
        logger.error("LLM error: %s", exc)
        obs = create_observation(
            agent_name="python",
            status="error",
            summary=f"Python code generation failed: {exc}",
            artifacts={"python_code": "", "data_summary": ""},
            error=str(exc),
        )
        return {
            "current_agent": "python",
            "error": f"Python code generation failed: {exc}",
            "agent_steps": state.get("agent_steps", []) + ["python"],
            "last_observation": obs,
        }

    code_match = re.search(r"<python>(.*?)</python>", raw, re.DOTALL)
    python_code = code_match.group(1).strip() if code_match else raw.strip()
    logger.info("generated Python (%d chars)", len(python_code))

    session_id = state.get("session_id", state.get("run_id", "default"))
    exec_result = await execute_code(python_code, session_id)
    if "code_error" in exec_result or "error" in exec_result:
        err = exec_result.get("code_error") or exec_result.get("error")
        logger.error("sandbox execution failed: %s", err)

        data_discovery_error = extract_data_discovery_error(err)

        obs = create_observation(
            agent_name="python",
            status="error",
            summary=f"Python execution failed: {err}",
            artifacts={
                "python_code": python_code,
                "data_summary": "",
                "data_discovery_error": data_discovery_error,
            },
            error=err,
        )
        return {
            "current_agent": "python",
            "python_code": python_code,
            "error": f"Python execution error: {err}",
            "data_summary": f"Execution error: {err}",
            "result_var_names": [],
            "agent_steps": state.get("agent_steps", []) + ["python"],
            "last_observation": obs,
        }

    df_var = await get_variable(session_id, "df_result")
    data_summary = _build_data_summary(df_var)

    logger.info("exit success summary=%r", data_summary.split("\n")[0] if data_summary else "")
    obs = create_observation(
        agent_name="python",
        status="success",
        summary=f"Python executed: {data_summary.split(chr(10))[0]}",
        artifacts={
            "python_code": python_code,
            "data_summary": data_summary,
            "result_var_names": ["df_result"],
        },
        error=None,
    )

    return {
        "current_agent": "python",
        "python_code": python_code,
        "data_summary": data_summary,
        "result_var_names": ["df_result"],
        "agent_steps": state.get("agent_steps", []) + ["python"],
        "last_observation": obs,
    }


def _build_data_summary(df_var) -> str:
    if not df_var or "result" not in df_var:
        return "No data returned"
    try:
        for item in df_var["result"]:
            if item.get("type") == "table":
                rows = json.loads(item["data"])
                if not rows:
                    return "Empty table result"
                columns = list(rows[0].keys())
                row_count = len(rows)
                header = " | ".join(columns)
                preview_lines = [
                    " | ".join(str(r.get(c, "")) for c in columns) for r in rows[:5]
                ]
                return (
                    f"Columns: {columns}\n"
                    f"Row count: {row_count}\n"
                    f"Preview ({min(5, row_count)} rows):\n"
                    f"{header}\n" + "\n".join(preview_lines)
                )
        return "Result available but no table data"
    except Exception as exc:
        return f"Data summary unavailable: {exc}"
