"""Shared helpers for detecting missing tables/columns in sandbox execution."""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

_DISCOVERY_PATTERNS: List[Tuple[str, str]] = [
    (r"table.*(?:not found|does not exist|doesn't exist)", "table_not_found"),
    (r"column.*(?:not found|does not exist|doesn't exist)", "column_not_found"),
    (r"catalog error", "catalog_error"),
    (r"unknown table", "unknown_table"),
    (r"unknown column", "unknown_column"),
    (r"no schema", "no_schema"),
    (r"relation.*does not exist", "relation_not_found"),
    (r"keyerror", "column_not_found"),
]


def extract_data_discovery_error(error_msg: str) -> Optional[str]:
    """Return a normalized message when failure is due to missing schema objects."""
    if not error_msg:
        return None

    error_lower = error_msg.lower()
    for pattern, error_type in _DISCOVERY_PATTERNS:
        if re.search(pattern, error_lower):
            return f"Data discovery error ({error_type}): {error_msg}"
    return None
