"""Scoped inputs and output guardrails for worker agents (LangGraph state isolation)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from agents.shared.state import AgentState, ExecutionPlanStep

# ---------------------------------------------------------------------------
# Role boundaries — canonical scope data. Consumed by the specialized-agent
# registry (specialized_agent._SCOPE); each worker's SYSTEM prompt carries the
# LLM-facing copy, so build_worker_user_message does NOT repeat it per call.
# ---------------------------------------------------------------------------

_ROLE_ALIASES = {
    "exec": "sql",
    "code_executor": "sql",
}

_SCOPE: Dict[str, Dict[str, str]] = {
    "sql": {
        "step_title": "Fetch data via SQL",
        "deliverable": "ONE DuckDB SQL query that retrieves the rows/columns needed for downstream steps.",
        "forbidden": (
            "Do NOT answer the user's question, write business insights, recommendations, "
            "interpretations, trend narratives, or create charts. "
            "EXPLANATION must be exactly one technical sentence about what the query selects."
        ),
    },
    "python": {
        "step_title": "Compute / transform data via Python",
        "deliverable": (
            "Python code that loads data from DuckDB views and materialises the answer in ``df_result``. "
            "Statistical computation only when this step requires it."
        ),
        "forbidden": (
            "Do NOT write business insights, recommendations, markdown reports, or print narrative analysis. "
            "Do NOT create matplotlib/seaborn charts — the viz agent handles visualization."
        ),
    },
    "eda": {
        "step_title": "Exploratory data analysis",
        "deliverable": (
            "A concise factual EDA narrative: shape, statistics, distributions, missing values, correlations."
        ),
        "forbidden": (
            "Do NOT write business recommendations, actionable advice, or answer 'why' questions. "
            "No Executive Summary or Key Findings sections."
        ),
    },
    "insight": {
        "step_title": "Business insights",
        "deliverable": "Exactly 3 business insights with High/Medium/Low impact labels.",
        "forbidden": "Do NOT write SQL, Python code, or create charts.",
    },
    "viz": {
        "step_title": "Data visualization",
        "deliverable": "Python matplotlib code that creates 1-2 focused charts.",
        "forbidden": (
            "Do NOT write business insights, recommendations, or long narrative text. "
            "Charts only."
        ),
    },
}

_INSIGHT_MARKERS = re.compile(
    r"\b("
    r"insight|recommend(?:ation)?s?|actionable|business implication|key finding|"
    r"executive summary|drivers?|because users? should|we suggest|you should|"
    r"strategic|next steps?"
    r")\b",
    re.I,
)

_CHART_IN_PYTHON = re.compile(r"\b(plt\.|matplotlib|seaborn|\.plot\(|\.bar\(|\.hist\()", re.I)

# Recommendation-style lines to strip from EDA output. Deliberately narrow:
# factual stat language ("the distribution suggests skew", "outliers should be
# checked") must survive, so "suggest"/"should" are NOT matched here.
_ADVICE_LINE = re.compile(
    r"\b(recommend(?:ation)?s?|actionable|action items?|next steps?)\b",
    re.I,
)


def get_planner_action_input(state: AgentState) -> Dict[str, Any]:
    """Latest planner ``action_input`` for the step being dispatched."""
    history = state.get("planner_history") or []
    if not history:
        return {}
    raw = history[-1].get("action_input") or {}
    return raw if isinstance(raw, dict) else {}


def _resolve_role(role: str) -> str:
    return _ROLE_ALIASES.get(role, role)


def _plan_step_for_action(state: AgentState, action: str) -> Optional[ExecutionPlanStep]:
    """First execution-plan step whose ``action`` matches (any status)."""
    for step in state.get("execution_plan") or []:
        if step.get("action") == action:
            return step
    return None


# Roles that emit SQL against the DuckDB views and therefore need the exact,
# copy-pasteable view names (prevents catalog-qualified hallucinations like
# ``'<id>'.main.<table>``).
_DATA_ROLES = {"sql", "python", "viz"}


def _available_view_names(state: AgentState) -> List[str]:
    """Exact DuckDB view names the worker may query, in registration order."""
    names: List[str] = []
    for ds in state.get("datasources") or []:
        for view in ds.get("view_names") or []:
            if view and view not in names:
                names.append(view)
    if names:
        return names
    # Fallback: parse "## Table: <name>" headers from the schema markdown.
    for match in re.findall(r"^##\s*Table:\s*(.+?)\s*$", state.get("schema_info") or "", re.M):
        cleaned = match.strip().strip('"')
        if cleaned and cleaned not in names:
            names.append(cleaned)
    return names


def build_worker_user_message(state: AgentState, role: str) -> str:
    """Narrow user message: the worker's assigned step + the query as context only.

    Role boundaries (deliverable, out-of-scope) are enforced by the worker's
    system prompt, so they are not repeated here — this keeps the per-call
    message small while the system prompt stays static and cacheable.
    """
    role = _resolve_role(role)
    scope = _SCOPE.get(role)
    if not scope:
        return state.get("query", "")

    user_query = (state.get("query") or "").strip()
    action_input = get_planner_action_input(state)
    planner_note = (
        action_input.get("task")
        or action_input.get("note")
        or action_input.get("objective")
        or ""
    ).strip()

    # Prefer the description of the plan step actually being dispatched
    # (``current_action`` covers the exec→sql/python router); fall back to role.
    current_action = state.get("current_action") or role
    plan_step = _plan_step_for_action(state, current_action) or _plan_step_for_action(state, role)
    step_desc = (plan_step or {}).get("description") or scope["step_title"]

    lines = [
        f"## Your assigned step: {scope['step_title']}",
        step_desc,
    ]
    if role in _DATA_ROLES:
        views = _available_view_names(state)
        if views:
            quoted = ", ".join(f'"{v}"' for v in views)
            lines += [
                "",
                f'Available tables — query these EXACT view names only, with no catalog/schema prefix: {quoted}',
            ]
    lines += [
        "",
        "Original user question (context only — do NOT answer it yourself; later steps do):",
        user_query,
    ]
    if planner_note:
        lines.extend(["", f"Planner instruction: {planner_note}"])
    return "\n".join(lines)


def sanitize_sql_explanation(explanation: str) -> str:
    """Guardrail: SQL worker explanation is one technical sentence, no insight prose."""
    text = (explanation or "").strip()
    if not text:
        return ""

    # Keep only the first sentence.
    sentence_end = re.search(r"[.!?](?:\s|$)", text)
    if sentence_end:
        text = text[: sentence_end.end()].strip()

    if _INSIGHT_MARKERS.search(text):
        return "Query retrieves the columns and rows required for the assigned data-fetch step."

    if len(text) > 220:
        text = text[:217].rstrip() + "..."
    return text


def check_python_scope_violations(code: str) -> List[str]:
    """Detect chart/narrative patterns that belong to other workers."""
    violations: List[str] = []
    if _CHART_IN_PYTHON.search(code):
        violations.append("chart code (use viz agent instead)")
    if re.search(r"print\s*\(\s*['\"].{80,}", code):
        violations.append("long narrative print (insights belong in insight agent)")
    return violations


def sanitize_eda_output(text: str) -> str:
    """Strip recommendation-style sections from EDA output."""
    if not text:
        return text

    lines = text.splitlines()
    kept: List[str] = []
    for line in lines:
        if _ADVICE_LINE.search(line):
            continue
        kept.append(line)
    cleaned = "\n".join(kept).strip()
    return cleaned or text
