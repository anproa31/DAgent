"""Risk tiering for generated Python before sandbox execution (solution.md §5).

SAFE   — pure pandas/numpy/scipy: auto-run.
MEDIUM — file I/O: require human approval (SSE ``python_review_required``).
HIGH   — network / os / subprocess: block with an error observation.
"""

from __future__ import annotations

import re

SAFE = "safe"
MEDIUM = "medium"
HIGH = "high"

# Network / process / OS access — never auto-run, and not worth prompting for.
_HIGH_PATTERNS = (
    re.compile(r"\bimport\s+os\b"),
    re.compile(r"\bfrom\s+os\b"),
    re.compile(r"\bimport\s+subprocess\b"),
    re.compile(r"\b(import|from)\s+(requests|urllib|httpx|socket|aiohttp)\b"),
    re.compile(r"\bos\.(system|popen|remove|rename|environ)\b"),
    re.compile(r"\b__import__\s*\("),
    re.compile(r"\b(eval|exec)\s*\("),
)

# Filesystem writes — plausibly legitimate, but the user should approve.
_MEDIUM_PATTERNS = (
    re.compile(r"\bopen\s*\("),
    re.compile(r"\b\.to_(csv|excel|parquet|json|pickle|sql)\s*\("),
    re.compile(r"\b(import|from)\s+pathlib\b"),
    re.compile(r"\bPath\s*\("),
    re.compile(r"\b\.write(text|bytes)?\s*\("),
)


def assess_python_risk(code: str) -> str:
    """Classify generated Python into a risk tier."""
    text = code or ""
    if any(p.search(text) for p in _HIGH_PATTERNS):
        return HIGH
    if any(p.search(text) for p in _MEDIUM_PATTERNS):
        return MEDIUM
    return SAFE
