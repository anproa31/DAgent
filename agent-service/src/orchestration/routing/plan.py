"""Structured execution plans and orchestration mode selection (DB-GPT AutoPlan-inspired)."""

from __future__ import annotations

import re
from typing import List, Literal, TypedDict

OrchestrationMode = Literal["FIXED", "AUTO_PLAN", "EXPLORE"]
PlanStepStatus = Literal["pending", "running", "done", "failed", "skipped"]

_TERMINAL_ACTIONS = frozenset({"generate_result", "finish"})

_EXPLORE_PATTERNS: List[re.Pattern] = [
    re.compile(
        r"\b(explore|deep[\s-]?dive|comprehensive|thorough|investigate|"
        r"full[\s-]?analysis|in[\s-]?depth|dig[\s-]?deeper|drill[\s-]?down)\b",
        re.I,
    ),
    re.compile(r"\b(and\s+(?:also\s+)?(?:analy[sz]e|explore|visuali[sz]e|chart))\b", re.I),
]

_STEP_DESCRIPTIONS = {
    "sql": "Fetch data via DuckDB SQL against registered datasources",
    "python": "Run Python analysis (pandas/numpy/scipy) against sandbox data",
    "eda": "Exploratory data analysis — distributions, correlations, quality checks",
    "insight": "Generate actionable business insights from findings",
    "viz": "Create matplotlib visualizations",
    "generate_result": "Compile artifacts into the final report",
}


class PlanStep(TypedDict, total=False):
    step_id: int
    action: str
    status: PlanStepStatus
    description: str
    rely: List[int]


def detect_explore_intent(query: str) -> bool:
    """True when the user explicitly asks for deeper exploration beyond a simple lookup."""
    if not query:
        return False
    return any(p.search(query) for p in _EXPLORE_PATTERNS)


def select_orchestration_mode(
    intent: str,
    query: str,
    *,
    is_replan: bool = False,
) -> OrchestrationMode:
    """Pick how strictly the planner must follow the orchestrator's plan."""
    if is_replan:
        return "EXPLORE"
    if detect_explore_intent(query):
        return "EXPLORE"
    if intent == "ANALYTICAL":
        return "AUTO_PLAN"
    return "FIXED"


def build_execution_plan(
    pipeline: List[str],
    intent: str,
    execution_mode: str,
) -> List[PlanStep]:
    """Convert a normalized pipeline into a dependency-aware execution plan."""
    worker_steps = [step for step in pipeline if step not in _TERMINAL_ACTIONS]
    if not worker_steps:
        worker_steps = [execution_mode or "sql"]

    plan: List[PlanStep] = []
    for index, action in enumerate(worker_steps):
        step_id = index + 1
        rely = [step_id - 1] if index > 0 else []
        plan.append(
            {
                "step_id": step_id,
                "action": action,
                "status": "pending",
                "description": _STEP_DESCRIPTIONS.get(action, f"Run {action}"),
                "rely": rely,
            }
        )

    terminal_rely = [plan[-1]["step_id"]] if plan else []
    plan.append(
        {
            "step_id": len(plan) + 1,
            "action": "generate_result",
            "status": "pending",
            "description": _STEP_DESCRIPTIONS["generate_result"],
            "rely": terminal_rely,
        }
    )
    return plan


def update_plan_from_reflection(
    plan: List[PlanStep],
    feedback: str,
    execution_mode: str,
) -> List[PlanStep]:
    """Insert missing worker steps suggested by reflection feedback."""
    feedback_lower = feedback.lower()
    additions: List[str] = []

    if any(k in feedback_lower for k in ("eda", "exploratory", "distribution", "missing values")):
        additions.append("eda")
    if any(k in feedback_lower for k in ("insight", "business", "actionable", "why", "recommend")):
        additions.append("insight")
    if any(k in feedback_lower for k in ("viz", "chart", "visual", "plot", "histogram")):
        additions.append("viz")

    existing = {step["action"] for step in plan if step["action"] not in _TERMINAL_ACTIONS}
    insert_before = _find_terminal_step(plan)
    new_steps: List[PlanStep] = []
    next_id = max((step["step_id"] for step in plan), default=0) + 1

    for action in additions:
        if action in existing:
            continue
        prev_id = plan[insert_before - 1]["step_id"] if insert_before > 0 else None
        new_steps.append(
            {
                "step_id": next_id,
                "action": action,
                "status": "pending",
                "description": _STEP_DESCRIPTIONS.get(action, f"Run {action}"),
                "rely": [prev_id] if prev_id else [],
            }
        )
        next_id += 1
        existing.add(action)

    if not new_steps:
        return plan

    updated = plan[:insert_before] + new_steps + plan[insert_before:]
    terminal = _find_terminal_step(updated)
    if terminal < len(updated):
        worker_ids = [
            step["step_id"]
            for step in updated[:terminal]
            if step["status"] != "skipped"
        ]
        updated[terminal]["rely"] = worker_ids[-1:] if worker_ids else []
    return updated


def mark_plan_step_status(
    plan: List[PlanStep],
    action: str,
    status: PlanStepStatus,
) -> List[PlanStep]:
    """Update the first matching pending/running step for an action."""
    updated: List[PlanStep] = []
    marked = False
    for step in plan:
        copy = dict(step)
        if (
            not marked
            and copy.get("action") == action
            and copy.get("status") in ("pending", "running", "failed")
        ):
            copy["status"] = status
            marked = True
        updated.append(copy)  # type: ignore[arg-type]
    return updated


def get_next_planned_action(plan: List[PlanStep]) -> str | None:
    """Return the next pending worker action, or generate_result if workers are done."""
    for step in plan:
        if step.get("status") == "pending" and step.get("action") not in _TERMINAL_ACTIONS:
            return step["action"]
    for step in plan:
        if step.get("status") == "pending" and step.get("action") in _TERMINAL_ACTIONS:
            return step["action"]
    return None


def get_remaining_plan_summary(plan: List[PlanStep]) -> List[str]:
    return [
        f"{step['step_id']}. {step['action']} ({step.get('status', 'pending')})"
        for step in plan
        if step.get("status") == "pending"
    ]


def format_plan_for_prompt(plan: List[PlanStep], orchestration_mode: OrchestrationMode) -> str:
    if not plan:
        return "(No execution plan — planner decides freely)"

    lines = [f"Orchestration mode: {orchestration_mode}"]
    for step in plan:
        rely = step.get("rely") or []
        rely_txt = f", depends on step(s) {rely}" if rely else ""
        lines.append(
            f"  Step {step['step_id']}: {step['action']} [{step.get('status', 'pending')}]"
            f" — {step.get('description', '')}{rely_txt}"
        )

    mode_rules = {
        "FIXED": "Follow pending steps in order. Only deviate for error recovery.",
        "AUTO_PLAN": "Use the plan as default routing; adapt when observations require it.",
        "EXPLORE": "Plan is a starting point — add/reorder steps freely to satisfy the query.",
    }
    lines.append(f"Mode rule: {mode_rules.get(orchestration_mode, '')}")
    return "\n".join(lines)


def _find_terminal_step(plan: List[PlanStep]) -> int:
    for index, step in enumerate(plan):
        if step.get("action") in _TERMINAL_ACTIONS:
            return index
    return len(plan)
