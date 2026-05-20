"""Input validation and execution restrictions."""
from __future__ import annotations

import re
from typing import List

from security.utils import SecurityUtils

_CONNECTION_REASSIGNMENT = re.compile(
    r"^(duckdb_conn|duck|engine)\s*=.*\n?",
    flags=re.MULTILINE,
)


def sanitize_user_code(code: str) -> str:
    """Disallow reassigning the shared DuckDB connection handles."""
    code = code.replace("%@", "\\")
    return _CONNECTION_REASSIGNMENT.sub("", code)


def validate_user_code(code: str, language: str = "python") -> List[str]:
    """Return security warnings for submitted code."""
    return SecurityUtils.validate_code(code, language)
