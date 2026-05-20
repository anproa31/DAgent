"""Compact planner context (solution.md §1 Fix 1/3 and §8).

The planner reads *summaries and hints only* — never raw worker data. This
keeps the context window bounded no matter how large SQL/Python results get,
and gives the ReAct loop the failure memory it needs to stop retrying dead ends.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from agents.shared.state import AgentState, PlannerStep
from config.settings import PLANNER_RECENT_OBSERVATIONS

_DATA_REF_KEYS = ("result_var_names", "viz_var_names", "view_names")


def collect_observations(state: AgentState) -> List[Dict[str, Any]]:
    """Chronological worker observations, newest last (deduped against latest)."""
    history: List[PlannerStep] = state.get("planner_history") or []
    observations: List[Dict[str, Any]] = [
        step["observation"] for step in history if step.get("observation")
    ]

    last = state.get("last_observation") or {}
    if last and (not observations or observations[-1] is not last):
        # last_observation is the freshest result, not yet attached to a step.
        if not observations or observations[-1].get("summary") != last.get("summary"):
            observations.append(last)
    return observations


def _data_ref_summary(artifacts: Dict[str, Any]) -> Optional[str]:
    if not artifacts:
        return None
    parts: List[str] = []
    for key in _DATA_REF_KEYS:
        names = artifacts.get(key)
        if names:
            parts.append(f"{key}={list(names)}")
    rows = artifacts.get("rows") or artifacts.get("row_count")
    cols = artifacts.get("columns")
    if rows is not None:
        shape = f"rows={rows}"
        if isinstance(cols, list):
            shape += f", cols={len(cols)}"
        parts.append(shape)
    return "; ".join(parts) if parts else None


def format_failed_attempts(observations: List[Dict[str, Any]]) -> str:
    """Render the '## Failed attempts' block (solution.md §1 Fix 3)."""
    lines: List[str] = []
    for idx, obs in enumerate(observations, start=1):
        if obs.get("status") != "error":
            continue
        agent = obs.get("agent", "?")
        reason = obs.get("error") or obs.get("summary") or "unknown error"
        lines.append(f"- {agent} [step {idx}]: {str(reason)[:160]}")
    if not lines:
        return ""
    return "## Failed attempts (do not retry the same way)\n" + "\n".join(lines)


def format_task_progress(completed_actions: list, execution_plan: list) -> str:
    """DB-GPT-style task progress injected into the planner prompt.

    Shows ✅ for completed steps and ⏳ for pending ones so the LLM knows
    which actions have already run and must not be repeated.
    """
    if not execution_plan:
        return ""
    lines = ["## Task progress (DO NOT re-run ✅ steps):"]
    for step in execution_plan:
        action = step.get("action", "")
        if action in ("generate_result", "finish"):
            continue
        mark = "✅" if action in completed_actions else "⏳"
        lines.append(f"  {mark} {action}")
    return "\n".join(lines)


def build_planner_context(
    state: AgentState,
    completed_actions: list | None = None,
    execution_plan: list | None = None,
    *,
    recent: int = PLANNER_RECENT_OBSERVATIONS,
) -> str:
    """Summarised observation context for the planner prompt.

    Rule: planner reads summaries + next_hint + data references only.
    """
    observations = collect_observations(state)

    # Resolve defaults from state when not passed explicitly (backward compat)
    if completed_actions is None:
        completed_actions = state.get("completed_actions") or []
    if execution_plan is None:
        execution_plan = state.get("execution_plan") or []

    if not observations:
        progress = format_task_progress(completed_actions, execution_plan)
        base = "(No observations yet — this is the first step.)"
        return f"{progress}\n\n{base}" if progress else base

    sections: List[str] = []

    # Prepend DB-GPT-style task progress so the planner sees it first
    progress = format_task_progress(completed_actions, execution_plan)
    if progress:
        sections.append(progress)

    older = observations[:-recent] if len(observations) > recent else []
    if older:
        completed = [o.get("agent", "?") for o in older if o.get("status") == "success"]
        if completed:
            sections.append(f"Completed earlier: {', '.join(completed)}")

    recent_obs = observations[-recent:]
    for obs in recent_obs:
        line = f"[{obs.get('agent', '?')}] {obs.get('status', '?')}: {obs.get('summary', '')}"
        sections.append(line)
        if obs.get("status") == "error" and obs.get("error"):
            sections.append(f"  Error: {str(obs['error'])[:160]}")
        if obs.get("next_hint"):
            sections.append(f"  Hint: {obs['next_hint']}")
        ref = _data_ref_summary(obs.get("artifacts") or {})
        if ref:
            sections.append(f"  Data available: {ref}")

    failed = format_failed_attempts(observations)
    if failed:
        sections.append(failed)

    return "\n".join(sections)
