"""ReAct planner node — brain phase of the agent loop (plan + route)."""

from __future__ import annotations

import asyncio

from agents.orchestrator.planner.analytics_react_agent import MAX_PLANNER_STEPS, get_analytics_react_agent
from agents.orchestrator.planner.history import format_rl_suggestion
from agents.orchestrator.planner.plan_tracker import sync_plan_with_completed, update_completed_actions
from agents.orchestrator.reflection.memory import get_policy_suggestion
from agents.shared.agent_anatomy import (
    LoopPhase,
    StopReason,
    consume_budget,
    evaluate_stop,
    phase_update,
)
from agents.shared.guardrails import budget_cost_for_planner_step, gate_planner_action
from agents.shared.perceive import format_perceived_task_context, perceive, perceive_state_patch
from agents.shared.state import AgentState, PlannerStep
from orchestration.streaming import current_run_var
from utils.agent_logger import get_logger

logger = get_logger("planner")


async def planner_node(state: AgentState) -> dict:
    """Brain phase: perceive context → plan next action → guardrail gate → route."""
    planner_history = state.get("planner_history", [])
    last_observation = state.get("last_observation", {})
    planner_step_index = state.get("planner_step_index", 0)
    is_first_step = len(planner_history) == 0

    logger.info("enter step=%d first=%s phase=brain", planner_step_index, is_first_step)

    # --- Perceive: short-term observations + long-term memory (every iteration) ---
    perceived = await perceive(state, refresh_schema=is_first_step)
    perceive_patch = perceive_state_patch(perceived)

    completed_actions = update_completed_actions(state)
    execution_plan = sync_plan_with_completed(
        state.get("execution_plan") or [],
        completed_actions,
    )
    orchestration_mode = state.get("orchestration_mode", "AUTO_PLAN")

    # --- Stop conditions: done | max_iters | budget ---
    stop = evaluate_stop(state)
    if stop.should_stop and stop.forced_action:
        logger.info("stop reason=%s msg=%s", stop.reason, stop.message)
        new_step: PlannerStep = {
            "thought": stop.message,
            "action": stop.forced_action,
            "action_input": {},
        }
        budget = consume_budget(state, budget_cost_for_planner_step())
        return {
            **perceive_patch,
            **phase_update(LoopPhase.BRAIN),
            "current_action": stop.forced_action,
            "orchestration_mode": orchestration_mode,
            "execution_plan": execution_plan,
            "completed_actions": completed_actions,
            "planner_history": planner_history + [new_step],
            "planner_step_index": planner_step_index + 1,
            "run_budget": budget,
            "completion_reason": (
                stop.reason.value if stop.reason and stop.reason != StopReason.DONE else state.get("completion_reason")
            ),
            "agent_steps": state.get("agent_steps", []) + ["planner"],
        }

    rl_suggestion = get_policy_suggestion(state.get("query", ""), state.get("intent", "RETRIEVAL"))
    rl_context = format_rl_suggestion(rl_suggestion) if rl_suggestion else ""

    task_context = format_perceived_task_context(
        state,
        perceived,
        rl_context=rl_context,
        step_index=planner_step_index,
        max_steps=MAX_PLANNER_STEPS,
    )

    agent = get_analytics_react_agent(
        base_url=state.get("base_url", ""),
        api_key=state.get("api_key", ""),
        model=state.get("model", ""),
    )

    ctx_token = current_run_var.set((state.get("run_id", ""), "planner"))
    try:
        decision = await asyncio.to_thread(agent.plan_next, state, task_context=task_context)
    except Exception as exc:
        logger.warning("ReAct planner error, using fallback: %s", exc)
        decision = (
            {"thought": "ReAct error, defaulting to exec", "action": "exec", "action_input": {}}
            if is_first_step
            else {
                "thought": "ReAct error, defaulting to generate_result",
                "action": "generate_result",
                "action_input": {},
            }
        )
    finally:
        current_run_var.reset(ctx_token)

    action = decision.get("action", "exec")
    thought = decision.get("thought", "")
    action_input = decision.get("action_input", {})

    # Guardrail gate: validate → scope → budget
    gate = gate_planner_action(state, action, action_input)
    if gate.normalized_action:
        action = gate.normalized_action
    if gate.normalized_input is not None:
        action_input = gate.normalized_input
    if gate.reason and gate.reason not in thought:
        thought = f"{thought} [{gate.reason}]".strip()

    intent = state.get("intent", "RETRIEVAL")
    execution_mode = state.get("execution_mode", "sql")
    if execution_mode not in ("sql", "python"):
        execution_mode = "sql"

    logger.info("exit thought=%r action=%s", thought[:80], action)

    new_step = {
        "thought": thought,
        "action": action,
        "action_input": action_input,
    }
    if last_observation and planner_history:
        new_step["observation"] = last_observation

    budget = consume_budget(state, budget_cost_for_planner_step())

    return {
        **perceive_patch,
        **phase_update(LoopPhase.BRAIN),
        "current_action": action,
        "intent": intent,
        "execution_mode": execution_mode,
        "orchestration_mode": orchestration_mode,
        "execution_plan": execution_plan,
        "completed_actions": completed_actions,
        "planner_history": planner_history + [new_step],
        "planner_step_index": planner_step_index + 1,
        "run_budget": budget,
        "agent_steps": state.get("agent_steps", []) + ["planner"],
    }
