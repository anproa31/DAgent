"""Web data discovery with human-in-the-loop approval before registration."""

from __future__ import annotations

from langgraph.types import interrupt

from agents.shared.observations import create_observation, observation_from_tool_result
from agents.shared.state import AgentState
from agents.shared.web_discover_policy import needs_web_discover
from context.context_engine import get_enhanced_context
from context.schema_service import (
    combined_markdown_from_payload,
    fetch_schema_payload,
    get_datasources,
)
from tools.executor import run_tool
from utils.agent_logger import get_logger

logger = get_logger("web_discover_agent")


async def _refresh_schema_state(state: AgentState) -> dict:
    schema_payload = await fetch_schema_payload()
    schema_info = combined_markdown_from_payload(schema_payload)
    datasources = await get_datasources()
    enhanced_context = await get_enhanced_context(
        schema_payload.get("context", "") if schema_payload else "",
        state.get("query", ""),
        datasources=datasources or None,
        fallback=schema_info,
    )
    return {
        "schema_info": schema_info,
        "enhanced_context": enhanced_context,
        "datasources": datasources,
    }


async def web_discover_agent_node(state: AgentState) -> dict:
    allowed, gate_reason = needs_web_discover(state)
    if not allowed:
        logger.info("skip web discover: %s", gate_reason)
        obs = create_observation(
            agent_name="web_discover",
            status="skipped",
            summary=f"Web discovery skipped: {gate_reason}",
            artifacts={"gate_reason": gate_reason},
        )
        return {
            "current_agent": "web_discover",
            "agent_steps": state.get("agent_steps", []) + ["web_discover"],
            "last_observation": obs,
        }

    planner_history = state.get("planner_history") or []
    action_input = planner_history[-1].get("action_input", {}) if planner_history else {}

    query = (action_input.get("query") or state.get("query") or "").strip()
    direct_url = action_input.get("url") or action_input.get("source_url")
    name = action_input.get("name")
    session_id = state.get("session_id", state.get("run_id", "default"))

    logger.info("enter query=%r url=%s reason=%s", query[:100], direct_url or "(search)", gate_reason)

    proposal = await run_tool(
        session_id,
        "propose_web_data",
        query=query or direct_url,
        url=direct_url,
        model=state.get("model"),
        base_url=state.get("base_url"),
        api_key=state.get("api_key"),
    )

    if not proposal.success:
        obs = observation_from_tool_result("web_discover", "propose_web_data", proposal)
        return {
            "current_agent": "web_discover",
            "agent_steps": state.get("agent_steps", []) + ["web_discover"],
            "last_observation": obs,
            "error": proposal.error,
        }

    selected_urls = proposal.data.get("selected_urls") or []
    candidates = proposal.data.get("candidates") or []

    approval = interrupt(
        {
            "type": "web_datasource_review",
            "query": query,
            "reason": gate_reason,
            "candidates": candidates,
            "selected_urls": selected_urls,
            "proposed_name": name,
        }
    )

    approved = approval.get("approved", False)
    rejection_reason = approval.get("reason", "")
    approved_urls = approval.get("selected_urls") or selected_urls
    approved_name = approval.get("name") or name

    logger.info("HITL web discover approved=%s urls=%d", approved, len(approved_urls))

    if not approved:
        obs = create_observation(
            agent_name="web_discover",
            status="rejected",
            summary=f"Web datasource import rejected: {rejection_reason or 'User declined'}",
            artifacts={
                "web_discover_proposal": {
                    "query": query,
                    "reason": gate_reason,
                    "candidates": candidates,
                    "selected_urls": selected_urls,
                },
                "web_discover_approved": False,
            },
            error=rejection_reason or "User rejected web datasource import",
        )
        return {
            "current_agent": "web_discover",
            "web_discover_approved": False,
            "web_discover_rejection_reason": rejection_reason,
            "web_discover_proposal": obs["artifacts"]["web_discover_proposal"],
            "agent_steps": state.get("agent_steps", []) + ["web_discover"],
            "last_observation": obs,
        }

    if not approved_urls:
        obs = create_observation(
            agent_name="web_discover",
            status="error",
            summary="Web datasource import approved but no URLs were selected",
            artifacts={"web_discover_approved": True},
            error="No URLs selected",
        )
        return {
            "current_agent": "web_discover",
            "web_discover_approved": True,
            "agent_steps": state.get("agent_steps", []) + ["web_discover"],
            "last_observation": obs,
        }

    register_result = await run_tool(
        session_id,
        "register_web_data",
        urls=approved_urls,
        name=approved_name,
        query=query,
    )

    if not register_result.success:
        obs = observation_from_tool_result("web_discover", "register_web_data", register_result)
        return {
            "current_agent": "web_discover",
            "web_discover_approved": True,
            "agent_steps": state.get("agent_steps", []) + ["web_discover"],
            "last_observation": obs,
            "error": register_result.error,
        }

    schema_patch = await _refresh_schema_state(state)
    view_names = register_result.data.get("view_names") or []

    obs = observation_from_tool_result("web_discover", "register_web_data", register_result)
    obs["summary"] = register_result.data.get("summary", obs["summary"])
    obs["artifacts"]["view_names"] = view_names
    obs["artifacts"]["web_discover_approved"] = True
    obs["artifacts"]["gate_reason"] = gate_reason

    logger.info("exit registered views=%s", view_names)

    return {
        "current_agent": "web_discover",
        "web_discover_approved": True,
        "web_discover_rejection_reason": "",
        "agent_steps": state.get("agent_steps", []) + ["web_discover"],
        "last_observation": obs,
        **schema_patch,
    }
