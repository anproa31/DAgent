"""Python-first execution path for pandas/numpy/scipy analytics."""

from __future__ import annotations

import re

from langgraph.types import interrupt

from agents.executor.python_risk import HIGH, MEDIUM, assess_python_risk
from agents.shared.data_discovery import extract_data_discovery_error
from agents.shared.observations import create_observation, observation_from_tool_result
from agents.shared.state import AgentState
from tools.executor import run_tool
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

    # Risk-tiered review before execution (solution.md §5).
    risk = assess_python_risk(python_code)
    logger.info("python risk tier=%s", risk)

    if risk == HIGH:
        obs = create_observation(
            agent_name="python",
            status="error",
            summary="Blocked: high-risk Python (network/os/subprocess)",
            artifacts={"python_code": python_code, "python_risk": HIGH, "data_summary": ""},
            error="High-risk Python (network/os/subprocess) blocked by policy",
            next_hint="Rewrite using only pandas/numpy/scipy on the DuckDB views — no os/network/subprocess.",
        )
        return {
            "current_agent": "python",
            "python_code": python_code,
            "python_risk": HIGH,
            "error": "High-risk Python blocked by policy",
            "data_summary": "",
            "result_var_names": [],
            "agent_steps": state.get("agent_steps", []) + ["python"],
            "last_observation": obs,
        }

    if risk == MEDIUM:
        approval = interrupt(
            {
                "type": "python_review",
                "code": python_code,
                "risk": MEDIUM,
                "query": state["query"],
            }
        )
        approved = approval.get("approved", False)
        edited_code = (approval.get("code") or python_code).strip()
        rejection_reason = approval.get("reason", "")
        logger.info("python HITL approved=%s edited=%s", approved, edited_code != python_code)

        if not approved:
            obs = create_observation(
                agent_name="python",
                status="rejected",
                summary=f"Python execution rejected: {rejection_reason or 'User declined'}",
                artifacts={"python_code": edited_code, "python_risk": MEDIUM, "data_summary": ""},
                error=rejection_reason or "User rejected Python execution",
                next_hint="Adjust the approach per the user's feedback or try sql instead.",
            )
            return {
                "current_agent": "python",
                "python_code": edited_code,
                "python_risk": MEDIUM,
                "data_summary": "",
                "result_var_names": [],
                "agent_steps": state.get("agent_steps", []) + ["python"],
                "last_observation": obs,
            }
        python_code = edited_code

    exec_result = await run_tool(session_id, "execute_python", code=python_code)
    if not exec_result.success:
        err = exec_result.error or "Python execution failed"
        logger.error("sandbox execution failed: %s", err)
        data_discovery_error = extract_data_discovery_error(err)

        obs = observation_from_tool_result("python", "execute_python", exec_result)
        obs["artifacts"]["data_summary"] = ""
        obs["artifacts"]["data_discovery_error"] = data_discovery_error

        return {
            "current_agent": "python",
            "python_code": python_code,
            "error": f"Python execution error: {err}",
            "data_summary": f"Execution error: {err}",
            "result_var_names": [],
            "agent_steps": state.get("agent_steps", []) + ["python"],
            "last_observation": obs,
        }

    var_result = await run_tool(session_id, "get_variable", name="df_result")
    data_summary = var_result.data.get("data_summary", "No data returned")
    logger.info("exit success summary=%r", data_summary.split("\n")[0] if data_summary else "")

    obs = observation_from_tool_result("python", "execute_python", exec_result)
    obs["artifacts"]["data_summary"] = data_summary
    obs["artifacts"]["result_var_names"] = ["df_result"]

    return {
        "current_agent": "python",
        "python_code": python_code,
        "data_summary": data_summary,
        "result_var_names": ["df_result"],
        "agent_steps": state.get("agent_steps", []) + ["python"],
        "last_observation": obs,
    }
