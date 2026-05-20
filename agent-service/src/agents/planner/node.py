"""ReAct planner: decide the next single action based on observations."""

from __future__ import annotations

import json
import re

from agents.planner.history import compress_planner_history, format_rl_suggestion
from agents.planner.plan_tracker import (
    resolve_planner_action,
    sync_plan_with_completed,
    update_completed_actions,
)
from agents.shared.web_discover_policy import should_use_discover_action
from agents.reflection.memory import get_policy_suggestion
from agents.shared.state import AgentState, PlannerStep
from context.context_engine import get_enhanced_context
from context.schema_service import (
    combined_markdown_from_payload,
    fetch_schema_payload,
    get_datasources,
)
from orchestration.routing.plan import format_plan_for_prompt, get_remaining_plan_summary
from utils.agent_logger import get_logger
from utils.llm_client import chat_complete, get_async_client
from utils.prompts import PLANNER_SYSTEM, format_semantic_context_for_prompt

logger = get_logger("planner")

MAX_PLANNER_STEPS = 15


async def planner_node(state: AgentState) -> dict:
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

    just_completed_sql_after_approval = (
        last_observation.get("agent") == "code_executor"
        and last_observation.get("status") == "success"
        and last_observation.get("artifacts", {}).get("sql_approved")
    )

    if just_completed_sql_after_approval and is_replan_from_reflection:
        logger.info("cleared reflection_replan_reason after successful SQL execution")
        reflection_replan_reason = ""
        is_replan_from_reflection = False

    if is_replan_from_reflection:
        if not planner_history or planner_history[-1].get("action") == "generate_result":
            replan_count += 1

    completed_actions = update_completed_actions(state)
    execution_plan = sync_plan_with_completed(
        state.get("execution_plan") or [],
        completed_actions,
    )
    orchestration_mode = state.get("orchestration_mode", "AUTO_PLAN")

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

    if planner_step_index >= MAX_PLANNER_STEPS:
        logger.warning("max steps (%d) reached, forcing generate_result", MAX_PLANNER_STEPS)
        return {
            "current_action": "generate_result",
            "planner_step_index": planner_step_index,
            "current_agent": "planner",
            "agent_steps": state.get("agent_steps", []) + ["planner"],
        }

    client = get_async_client(state.get("base_url", ""), state.get("api_key", ""))
    model = state.get("model", "")
    ctx = format_semantic_context_for_prompt(enhanced_context)

    datasources_summary = "\n".join(
        f"- {ds.get('name')} ({ds.get('kind')}/{ds.get('type')}) "
        f"with views: {', '.join(ds.get('view_names', []))}"
        for ds in datasources
    ) or "(no datasources registered)"

    discover_allowed, discover_reason = should_use_discover_action(state)

    compressed_history = compress_planner_history(planner_history, keep_last_n=5)
    rl_suggestion = get_policy_suggestion(state.get("query", ""), state.get("intent", "RETRIEVAL"))
    rl_context = format_rl_suggestion(rl_suggestion) if rl_suggestion else "(No historical patterns available)"
    plan_context = format_plan_for_prompt(execution_plan, orchestration_mode)  # type: ignore[arg-type]
    remaining_steps = get_remaining_plan_summary(execution_plan)

    messages = [
        {"role": "system", "content": PLANNER_SYSTEM.format(MAX_PLANNER_STEPS=MAX_PLANNER_STEPS)},
        {
            "role": "user",
            "content": (
                f"Registered datasources:\n{datasources_summary}\n\n"
                f"Web discovery allowed: {discover_allowed}\n"
                f"Web discovery reason: {discover_reason or '(not needed — prefer sql/python on existing data)'}\n\n"
                f"Datasource schema:\n{schema_info}\n\n"
                f"Semantic context:\n{ctx}\n\n"
                f"User query: {state['query']}\n\n"
                f"Intent (if known): {state.get('intent', 'unknown')}\n\n"
                f"Execution mode (if known): {state.get('execution_mode', 'unknown')}\n\n"
                f"Orchestration mode: {orchestration_mode}\n\n"
                f"Execution plan:\n{plan_context}\n\n"
                f"Remaining plan steps: {', '.join(remaining_steps) or '(none — wrap up with generate_result)'}\n\n"
                f"Completed actions: {', '.join(completed_actions) or '(none)'}\n\n"
                f"Planner history (compressed):\n{compressed_history}\n\n"
                f"Last observation:\n{json.dumps(last_observation, indent=2) if last_observation else '(none)'}\n\n"
                f"Reflection feedback (if re-planning): {reflection_feedback}\n\n"
                f"Reflection replan reason (if re-planning): {reflection_replan_reason}\n\n"
                f"Step index: {planner_step_index} / {MAX_PLANNER_STEPS}\n\n"
                f"RL Policy Suggestion (from historical success patterns):\n{rl_context}\n\n"
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

    valid_actions = {"sql", "python", "discover_data", "eda", "insight", "viz", "generate_result", "finish"}
    if action not in valid_actions:
        logger.warning("invalid action %r, defaulting to sql", action)
        action = "sql"

    if action == "discover_data" and not discover_allowed:
        logger.info("discover_data blocked: %s", discover_reason)
        action = "sql"
        thought = (
            f"{thought} [discover_data unavailable: {discover_reason}. Using sql instead.]"
        ).strip()

    action, plan_note = resolve_planner_action(
        {**state, "execution_plan": execution_plan, "orchestration_mode": orchestration_mode},
        action,
        last_observation=last_observation,
    )
    if plan_note and plan_note not in thought:
        thought = f"{thought} [{plan_note}]".strip()

    if execution_mode not in ("sql", "python"):
        execution_mode = "sql"

    logger.info("exit thought=%r action=%s intent=%s", thought[:80], action, intent)

    new_step: PlannerStep = {
        "thought": thought,
        "action": action,
        "action_input": action_input,
    }

    if last_observation and planner_history:
        new_step["observation"] = last_observation

    return {
        "current_action": action,
        "intent": intent,
        "execution_mode": execution_mode,
        "orchestration_mode": orchestration_mode,
        "execution_plan": execution_plan,
        "completed_actions": completed_actions,
        "planner_history": planner_history + [new_step],
        "planner_step_index": planner_step_index + 1,
        "replan_count": replan_count,
        "current_agent": "planner",
        "agent_steps": state.get("agent_steps", []) + ["planner"],
        "schema_info": schema_info if is_first_step else state.get("schema_info"),
        "enhanced_context": enhanced_context if is_first_step else state.get("enhanced_context"),
        "datasources": datasources if is_first_step else state.get("datasources"),
    }
