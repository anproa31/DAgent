import json
import re
from typing import Any, Dict, Optional

from agents.state import AgentState, PlannerStep
from services.context_engine import get_enhanced_context
from services.schema_service import (
    combined_markdown_from_payload,
    fetch_schema_payload,
    get_datasources,
)
from utils.agent_logger import get_logger
from utils.llm_client import chat_complete, get_async_client
from utils.prompts import PLANNER_SYSTEM, format_semantic_context_for_prompt

logger = get_logger("planner")


MAX_PLANNER_STEPS = 15


async def planner_node(state: AgentState) -> dict:
    """ReAct planner: decide the next single action based on observations so far.

    On first run: fetch schema/context, classify intent, choose first action.
    On subsequent runs: read planner_history + last_observation, decide next action.
    On reflection fail: use reflection_replan_reason to guide re-plan.
    """
    planner_history = state.get("planner_history", [])
    last_observation = state.get("last_observation", {})
    reflection_feedback = state.get("reflection_feedback", "")
    reflection_replan_reason = state.get("reflection_replan_reason", "")
    replan_count = state.get("replan_count", 0)
    planner_step_index = state.get("planner_step_index", 0)

    is_first_step = len(planner_history) == 0
    is_replan_from_reflection = bool(reflection_replan_reason)

    logger.info(
        "enter step=%d first=%s replan=%s",
        planner_step_index,
        is_first_step,
        is_replan_from_reflection,
    )

    # Increment replan_count when re-planning from reflection
    if is_replan_from_reflection:
        # Only increment once per reflection cycle (check if we already incremented)
        if not planner_history or planner_history[-1].get("action") == "generate_result":
            replan_count += 1

    # Fetch schema/context on first step only
    if is_first_step:
        tables_arg = state.get("tables")
        schema_payload = await fetch_schema_payload(tables_arg)

        schema_info = (state.get("schema_info") or "").strip()
        if not schema_info:
            if schema_payload:
                schema_info = combined_markdown_from_payload(schema_payload, tables_arg)
            else:
                schema_info = "Schema unavailable"

        datasources = state.get("datasources") or await get_datasources()

        raw_context = ""
        if schema_payload:
            ctx = schema_payload.get("context")
            if isinstance(ctx, str):
                raw_context = ctx

        fallback_enhanced = raw_context.strip() or schema_info
        enhanced_context = await get_enhanced_context(
            raw_context,
            state.get("query", ""),
            datasources=datasources or None,
            fallback=fallback_enhanced,
        )
    else:
        schema_info = state.get("schema_info", "")
        enhanced_context = state.get("enhanced_context", "")
        datasources = state.get("datasources", [])

    # Check step limit
    if planner_step_index >= MAX_PLANNER_STEPS:
        logger.warning("max steps (%d) reached, forcing generate_result", MAX_PLANNER_STEPS)
        return {
            "current_action": "generate_result",
            "planner_step_index": planner_step_index,
            "current_agent": "planner",
            "agent_steps": state.get("agent_steps", []) + ["planner"],
        }

    # Build prompt context
    client = get_async_client(state.get("base_url", ""), state.get("api_key", ""))
    model = state.get("model", "")
    ctx = format_semantic_context_for_prompt(enhanced_context)

    datasources_summary = "\n".join(
        f"- {ds.get('name')} ({ds.get('kind')}/{ds.get('type')}) "
        f"with views: {', '.join(ds.get('view_names', []))}"
        for ds in datasources
    ) or "(no datasources registered)"

    # Compress history for prompt (last N steps + full last observation)
    compressed_history = _compress_planner_history(planner_history, keep_last_n=5)

    messages = [
        {"role": "system", "content": PLANNER_SYSTEM.format(MAX_PLANNER_STEPS=MAX_PLANNER_STEPS)},
        {
            "role": "user",
            "content": (
                f"Registered datasources:\n{datasources_summary}\n\n"
                f"Datasource schema:\n{schema_info}\n\n"
                f"Semantic context:\n{ctx}\n\n"
                f"User query: {state['query']}\n\n"
                f"Intent (if known): {state.get('intent', 'unknown')}\n\n"
                f"Execution mode (if known): {state.get('execution_mode', 'unknown')}\n\n"
                f"Planner history (compressed):\n{compressed_history}\n\n"
                f"Last observation:\n{json.dumps(last_observation, indent=2) if last_observation else '(none)'}\n\n"
                f"Reflection feedback (if re-planning): {reflection_feedback}\n\n"
                f"Reflection replan reason (if re-planning): {reflection_replan_reason}\n\n"
                f"Step index: {planner_step_index} / {MAX_PLANNER_STEPS}\n\n"
                f"Decide the NEXT action:"
            ),
        },
    ]

    try:
        raw = await chat_complete(client, model, messages, temperature=0.1, log_tag="planner")
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise ValueError("No JSON found in planner response")
        decision = json.loads(match.group())
    except Exception as exc:
        logger.warning("LLM error, using fallback: %s", exc)
        # Fallback: if we have no actions yet, default to sql; otherwise generate_result
        if not planner_history:
            decision = {
                "thought": "LLM error, defaulting to sql as first step",
                "action": "sql",
                "action_input": {},
                "done": False,
            }
        else:
            decision = {
                "thought": "LLM error, defaulting to generate_result",
                "action": "generate_result",
                "action_input": {},
                "done": True,
            }

    action = decision.get("action", "sql")
    thought = decision.get("thought", "")
    action_input = decision.get("action_input", {})
    intent = decision.get("intent", state.get("intent", "RETRIEVAL")).upper()
    execution_mode = decision.get("execution_mode", state.get("execution_mode", "sql")).lower()

    # Validate action
    valid_actions = {"sql", "python", "eda", "insight", "viz", "generate_result", "finish"}
    if action not in valid_actions:
        logger.warning("invalid action %r, defaulting to sql", action)
        action = "sql"

    # Enforce execution mode consistency
    if execution_mode not in ("sql", "python"):
        execution_mode = "sql"

    logger.info("exit thought=%r action=%s intent=%s", thought[:80], action, intent)

    # Record this planner step
    new_step: PlannerStep = {
        "thought": thought,
        "action": action,
        "action_input": action_input,
    }

    # Update the last step with the observation if we have one
    if last_observation and planner_history:
        new_step["observation"] = last_observation

    return {
        "current_action": action,
        "intent": intent,
        "execution_mode": execution_mode,
        "planner_history": planner_history + [new_step],
        "planner_step_index": planner_step_index + 1,
        "replan_count": replan_count,
        "current_agent": "planner",
        "agent_steps": state.get("agent_steps", []) + ["planner"],
        "schema_info": schema_info if is_first_step else state.get("schema_info"),
        "enhanced_context": enhanced_context if is_first_step else state.get("enhanced_context"),
        "datasources": datasources if is_first_step else state.get("datasources"),
    }


def _compress_planner_history(history: list, keep_last_n: int = 5) -> str:
    """Compress planner history for prompt context.

    Returns a string summary of the last N steps.
    """
    if not history:
        return "(no prior steps)"

    recent = history[-keep_last_n:]
    lines = []
    for i, step in enumerate(recent):
        thought = step.get("thought", "")[:100]
        action = step.get("action", "")
        obs = step.get("observation", {})
        obs_summary = obs.get("summary", "(no summary)") if obs else "(pending)"
        lines.append(f"Step {i+1}: thought={thought}... | action={action} | observation={obs_summary}")

    return "\n".join(lines)


def route_after_planner(state: AgentState) -> str:
    """Route to the agent specified by the planner's current_action."""
    action = state.get("current_action", "sql")

    # Map planner actions to graph node names
    action_to_node = {
        "sql": "sql",
        "python": "python",
        "eda": "eda",
        "insight": "insight",
        "viz": "viz",
        "generate_result": "final_report",
        "finish": "final_report",
    }

    target = action_to_node.get(action, "sql")
    logger.info("route action=%s -> %s", action, target)
    return target


def create_observation(
    agent_name: str,
    status: str,
    summary: str,
    artifacts: Dict[str, Any],
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a structured observation for the planner.

    Args:
        agent_name: Name of the agent that just ran
        status: "success", "error", or "rejected"
        summary: Human-readable outcome
        artifacts: Dict of output artifacts (data_summary, result_var_names, etc.)
        error: Error message if status is "error"

    Returns:
        Structured observation dict
    """
    return {
        "agent": agent_name,
        "status": status,
        "summary": summary,
        "artifacts": artifacts,
        "error": error,
    }
