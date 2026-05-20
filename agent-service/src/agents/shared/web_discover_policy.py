"""When the agent may offer web data discovery."""

from __future__ import annotations

from typing import Tuple

from agents.shared.data_discovery import extract_data_discovery_error


def needs_web_discover(state: dict) -> Tuple[bool, str]:
    """Return (True, reason) when existing datasources are missing or insufficient."""
    datasources = state.get("datasources") or []
    if not datasources:
        return True, "No datasources are registered in the system."

    schema = (state.get("schema_info") or "").strip()
    if schema in ("", "Schema unavailable", "No schema registered"):
        return True, "Datasource schema is unavailable for this query."

    last = state.get("last_observation") or {}
    artifacts = last.get("artifacts") or {}

    discovery_err = artifacts.get("data_discovery_error")
    if discovery_err:
        return True, str(discovery_err)

    err = last.get("error") or ""
    normalized = extract_data_discovery_error(err)
    if normalized:
        return True, normalized

    if last.get("status") == "error" and last.get("agent") in {
        "code_executor",
        "python",
        "sql",
        "web_discover",
    }:
        summary = (last.get("summary") or err or "").lower()
        for hint in (
            "table",
            "column",
            "not found",
            "does not exist",
            "no schema",
            "catalog error",
        ):
            if hint in summary:
                return True, last.get("summary") or err or "Required data objects were not found."

    return False, ""


def should_use_discover_action(state: dict) -> Tuple[bool, str]:
    """Planner may choose discover_data only when policy allows it."""
    return needs_web_discover(state)
