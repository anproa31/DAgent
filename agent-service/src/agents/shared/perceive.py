"""Perceive phase: assemble short-term context + long-term memory (top-k).

Called at orchestrator entry and on every planner iteration so the brain always
sees fresh observations and compacted history.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from agents.orchestrator.planner.context_builder import build_planner_context
from agents.orchestrator.planner.memory_context import build_memory_context
from agents.shared.agent_anatomy import LoopPhase
from agents.shared.state import AgentState
from context.context_engine import get_enhanced_context
from context.schema_service import (
    combined_markdown_from_payload,
    fetch_schema_payload,
    get_datasources,
)
from agents.orchestrator.planner.plan import format_plan_for_prompt, get_remaining_plan_summary
from utils.agent_logger import get_logger
from utils.prompts import format_semantic_context_for_prompt

logger = get_logger("perceive")


@dataclass
class PerceivedContext:
    """Output of the perceive phase fed into the brain (planner / orchestrator)."""

    schema_info: str
    enhanced_context: str
    datasources: List[Dict[str, Any]]
    datasources_summary: str
    semantic_context: str
    memory_context: str
    observation_context: str
    plan_context: str
    remaining_steps: List[str]
    completed_actions: List[str]


async def perceive(state: AgentState, *, refresh_schema: bool = False) -> PerceivedContext:
    """Gather context from memory tiers and run state (short-term + long-term top-k)."""
    tables_arg = state.get("tables")
    schema_info = (state.get("schema_info") or "").strip()
    enhanced_context = (state.get("enhanced_context") or "").strip()
    datasources = state.get("datasources") or []

    if refresh_schema or not schema_info:
        schema_payload = await fetch_schema_payload(tables_arg)
        if not schema_info:
            if schema_payload:
                schema_info = combined_markdown_from_payload(schema_payload, tables_arg)
            else:
                schema_info = "Schema unavailable"

        if not datasources:
            datasources = await get_datasources()

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

    datasources_summary = "\n".join(
        f"- {ds.get('name')} ({ds.get('kind')}/{ds.get('type')}) "
        f"with views: {', '.join(ds.get('view_names', []))}"
        for ds in datasources
    ) or "(no datasources registered)"

    completed_actions = state.get("completed_actions") or []
    execution_plan = state.get("execution_plan") or []
    orchestration_mode = state.get("orchestration_mode", "AUTO_PLAN")

    observation_context = build_planner_context(
        state,
        completed_actions=completed_actions,
        execution_plan=execution_plan,
    )

    # Long-term memory: top-k KB / episodic / procedural (best-effort).
    memory_context = _retrieve_long_term_memory(state)

    return PerceivedContext(
        schema_info=schema_info,
        enhanced_context=enhanced_context,
        datasources=datasources,
        datasources_summary=datasources_summary,
        semantic_context=format_semantic_context_for_prompt(enhanced_context),
        memory_context=memory_context,
        observation_context=observation_context,
        plan_context=format_plan_for_prompt(execution_plan, orchestration_mode),  # type: ignore[arg-type]
        remaining_steps=get_remaining_plan_summary(execution_plan),
        completed_actions=completed_actions,
    )


def _retrieve_long_term_memory(state: AgentState) -> str:
    """Top-k retrieval from vector/KB/files via MemoryManager."""
    try:
        return build_memory_context(state)
    except Exception as exc:  # pragma: no cover
        logger.warning("long-term memory retrieval failed: %s", exc)
        return ""


def perceive_state_patch(ctx: PerceivedContext) -> Dict[str, Any]:
    """State fields updated after perceive (short-term working context)."""
    return {
        "loop_phase": LoopPhase.PERCEIVE.value,
        "schema_info": ctx.schema_info,
        "enhanced_context": ctx.enhanced_context,
        "datasources": ctx.datasources,
    }


def format_perceived_task_context(
    state: AgentState,
    ctx: PerceivedContext,
    *,
    rl_context: str = "",
    step_index: int = 0,
    max_steps: int = 15,
) -> str:
    """Compose the brain input from perceived context."""
    memory_section = (
        f"Long-term memory (top-k):\n{ctx.memory_context}\n\n" if ctx.memory_context else ""
    )
    return (
        f"User query: {state['query']}\n\n"
        f"Intent: {state.get('intent', 'unknown')}\n"
        f"Execution mode: {state.get('execution_mode', 'unknown')}\n"
        f"Orchestration mode: {state.get('orchestration_mode', 'AUTO_PLAN')}\n\n"
        f"Registered datasources:\n{ctx.datasources_summary}\n\n"
        f"Datasource schema:\n{ctx.schema_info}\n\n"
        f"Semantic context:\n{ctx.semantic_context}\n\n"
        f"{memory_section}"
        f"Execution plan:\n{ctx.plan_context}\n\n"
        f"Remaining plan steps: {', '.join(ctx.remaining_steps) or '(none)'}\n\n"
        f"Completed actions: {', '.join(ctx.completed_actions) or '(none)'}\n\n"
        f"Observations (summaries only):\n{ctx.observation_context}\n\n"
        f"RL policy suggestion:\n{rl_context or '(none)'}\n\n"
        f"Step index: {step_index} / {max_steps}"
    )
