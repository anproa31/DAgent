"""Deterministic retrieval-vs-analytical intent heuristics."""

from __future__ import annotations

import re
from typing import List

_RETRIEVAL_PATTERNS: List[re.Pattern] = [
    re.compile(r"^\s*(show|list|display|print|return|give\s+me|fetch|get|find)\b", re.I),
    re.compile(r"\b(first|last|top|bottom)\s+\d+\b", re.I),
    re.compile(
        r"\b\d+\s+(rows?|records?|entries|employees?|customers?|orders?|items?|users?|rows|records)\b",
        re.I,
    ),
    re.compile(r"^\s*(how many|count\s+of|number\s+of|total\s+number)\b", re.I),
    re.compile(r"^\s*(what\s+(?:is|are)\s+the)\s+", re.I),
]

_ANALYTICAL_PATTERNS: List[re.Pattern] = [
    re.compile(
        r"\b(why|how come|reason|cause|driver|correlat|trend|forecast|predict|insight|analy[sz]e|analysis|pattern|distribution|outlier|cluster|segment|t[\s-]?test|chi[\s-]?square|anova|regression|hypothesis|p[\s-]?value|significance)\b",
        re.I,
    ),
    re.compile(r"\b(compare|breakdown|over\s+time|by\s+\w+\s+over)\b", re.I),
    re.compile(r"\b(plot|chart|visuali[sz]e|graph|histogram|scatter|heatmap|bar\s+chart)\b", re.I),
    re.compile(r"\b(summary|summari[sz]e|report)\b", re.I),
]


def quick_classify(query: str) -> str:
    """Return ``RETRIEVAL``, ``ANALYTICAL``, or ``""`` (unknown)."""
    if not query or len(query.strip()) < 3:
        return ""
    if any(p.search(query) for p in _ANALYTICAL_PATTERNS):
        return "ANALYTICAL"
    if any(p.search(query) for p in _RETRIEVAL_PATTERNS):
        return "RETRIEVAL"
    return ""
