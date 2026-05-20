"""Reflection critic parsing and report context helpers."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional


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

        if action in ("sql", "python"):
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
            if artifacts.get("row_count"):
                parts.append(f"Rows: {artifacts['row_count']}")
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


def is_schema_complaint(complaint: str, datasources: list) -> bool:
    complaint_lower = complaint.lower()

    schema_keywords = [
        "table",
        "column",
        "datasource",
        "view",
        "schema",
        "not exist",
        "not found",
        "unavailable",
        "missing",
        "hr_employee_data",
    ]

    has_schema_keyword = any(kw in complaint_lower for kw in schema_keywords)

    available_tables = set()
    for ds in datasources:
        for view in ds.get("view_names", []):
            available_tables.add(view.lower())

    table_mentions = re.findall(r"['\"]?(\w+_?table\w*)['\"]?", complaint_lower)
    for table in table_mentions:
        if table not in available_tables:
            return True

    return has_schema_keyword


def parse_reflection_response(raw: str) -> dict:
    try:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass

    raw_lower = raw.lower()
    if "fail" in raw_lower or "reject" in raw_lower or "incomplete" in raw_lower:
        return {"pass": False, "feedback": raw[:500]}

    return {"pass": True, "feedback": raw[:500]}
