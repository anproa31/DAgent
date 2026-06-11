"""Report context helpers for the Reflection pattern."""

from __future__ import annotations

from typing import Optional


def flatten_report_content(report_content: list) -> str:
    if not report_content:
        return "(No report content generated)"

    sections = []
    for item in report_content:
        if isinstance(item, dict):
            if item.get("type") == "markdown":
                sections.append(item.get("content", ""))
            elif item.get("type") == "table":
                sections.append(f"[Table: {item.get('title', 'data')}]")
            elif item.get("type") == "image":
                sections.append(f"[Chart: {item.get('title', 'visualization')}]")
        elif isinstance(item, str):
            sections.append(item)

    return "\n\n".join(sections) if sections else "(Empty report)"


def build_data_context_from_history(planner_history: list) -> str:
    if not planner_history:
        return "(No execution history)"

    context_parts = []

    for i, step in enumerate(planner_history):
        action = step.get("action", "")
        observation = step.get("observation", {})

        if not observation:
            continue

        if action in ("exec", "sql", "python"):
            parts = []

            if observation.get("sql"):
                parts.append(f"Query: {observation['sql']}")
            elif observation.get("code_executed"):
                parts.append(f"Code executed: {observation['code_executed'][:200]}...")

            status = observation.get("status", "unknown")
            parts.append(f"Status: {status}")

            if observation.get("summary"):
                parts.append(f"Result: {observation['summary'][:300]}")

            artifacts = observation.get("artifacts", {})
            row_count = artifacts.get("row_count") or artifacts.get("rows")
            if row_count is not None:
                parts.append(f"Rows: {row_count}")
            if artifacts.get("data_summary"):
                parts.append(f"Data summary: {artifacts['data_summary'][:200]}")

            if parts:
                context_parts.append(f"### Step {i+1} ({action}):\n" + "\n".join(parts))

    return "\n\n".join(context_parts) if context_parts else "(No data context available)"


def extract_data_discovery_error_from_history(planner_history: list) -> Optional[str]:
    if not planner_history:
        return None

    for step in reversed(planner_history):
        obs = step.get("observation", {})
        if not obs:
            continue

        status = obs.get("status", "")
        summary = obs.get("summary", "")

        if status == "error" or "not found" in summary.lower():
            if (
                "table" in summary.lower()
                or "column" in summary.lower()
                or "datasource" in summary.lower()
            ):
                return summary

        artifacts = obs.get("artifacts", {})
        if artifacts.get("data_discovery_error"):
            return artifacts["data_discovery_error"]

    return None
