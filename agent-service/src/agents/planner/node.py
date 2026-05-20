"""ReAct planner node powered by agent-patterns ReActAgent."""

from __future__ import annotations

import asyncio
import json

from agents.planner.analytics_react_agent import MAX_PLANNER_STEPS, get_analytics_react_agent
from agents.planner.history import format_rl_suggestion
from agents.planner.plan_tracker import sync_plan_with_completed, update_completed_actions
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
from utils.prompts import format_semantic_context_for_prompt

logger = get_logger("planner")


async def planner_node(state: AgentState) -> dict:
    planner_history = state.get("planner_history", [])
    last_observation = state.get("last_observation", {})
    planner_step_index = state.get("planner_step_index", 0)
    is_first_step = len(planner_history) == 0

    logger.info("enter step=%d first=%s (agent-patterns ReAct)", planner_step_index, is_first_step)

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

    ctx = format_semantic_context_for_prompt(enhanced_context)
    datasources_summary = "\n".join(
        f"- {ds.get('name')} ({ds.get('kind')}/{ds.get('type')}) "
        f"with views: {', '.join(ds.get('view_names', []))}"
        for ds in datasources
    ) or "(no datasources registered)"

    rl_suggestion = get_policy_suggestion(state.get("query", ""), state.get("intent", "RETRIEVAL"))
    rl_context = format_rl_suggestion(rl_suggestion) if rl_suggestion else "(No historical patterns available)"
    plan_context = format_plan_for_prompt(execution_plan, orchestration_mode)  # type: ignore[arg-type]
    remaining_steps = get_remaining_plan_summary(execution_plan)

    task_context = (
        f"User query: {state['query']}\n\n"
        f"Intent: {state.get('intent', 'unknown')}\n"
        f"Execution mode: {state.get('execution_mode', 'unknown')}\n"
        f"Orchestration mode: {orchestration_mode}\n\n"
        f"Registered datasources:\n{datasources_summary}\n\n"
        f"Datasource schema:\n{schema_info}\n\n"
        f"Semantic context:\n{ctx}\n\n"
        f"Execution plan:\n{plan_context}\n\n"
        f"Remaining plan steps: {', '.join(remaining_steps) or '(none)'}\n\n"
        f"Completed actions: {', '.join(completed_actions) or '(none)'}\n\n"
        f"Last observation:\n{json.dumps(last_observation, indent=2) if last_observation else '(none)'}\n\n"
        f"RL policy suggestion:\n{rl_context}\n\n"
        f"Step index: {planner_step_index} / {MAX_PLANNER_STEPS}"
    )

    agent = get_analytics_react_agent(
        base_url=state.get("base_url", ""),
        api_key=state.get("api_key", ""),
        model=state.get("model", ""),
    )

    try:
        decision = await asyncio.to_thread(agent.plan_next, state, task_context=task_context)
    except Exception as exc:
        logger.warning("ReAct planner error, using fallback: %s", exc)
        decision = (
            {"thought": "ReAct error, defaulting to sql", "action": "sql", "action_input": {}}
            if is_first_step
            else {
                "thought": "ReAct error, defaulting to generate_result",
                "action": "generate_result",
                "action_input": {},
            }
        )

    action = decision.get("action", "sql")
    thought = decision.get("thought", "")
    action_input = decision.get("action_input", {})
    intent = state.get("intent", "RETRIEVAL")
    execution_mode = state.get("execution_mode", "sql")

    if execution_mode not in ("sql", "python"):
        execution_mode = "sql"

    logger.info("exit thought=%r action=%s", thought[:80], action)

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
        "current_agent": "planner",
        "agent_steps": state.get("agent_steps", []) + ["planner"],
        "schema_info": schema_info if is_first_step else state.get("schema_info"),
        "enhanced_context": enhanced_context if is_first_step else state.get("enhanced_context"),
        "datasources": datasources if is_first_step else state.get("datasources"),
    }
