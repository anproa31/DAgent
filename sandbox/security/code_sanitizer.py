"""Strip dangerous reassignments from user-submitted Python code."""
from __future__ import annotations

import re

_CONNECTION_REASSIGNMENT = re.compile(
    r"^(duckdb_conn|duck|engine)\s*=.*\n?",
    flags=re.MULTILINE,
)


def sanitize_user_code(code: str) -> str:
    """Disallow reassigning the shared DuckDB connection handles."""
    code = code.replace("%@", "\\")
    return _CONNECTION_REASSIGNMENT.sub("", code)
