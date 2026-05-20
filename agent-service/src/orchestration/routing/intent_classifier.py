"""Deterministic retrieval-vs-analytical intent heuristics.

Returns one of: "ANALYTICAL" | "LIGHT_ANALYTICAL" | "VIZ_ONLY" | "RETRIEVAL" | ""
  - ANALYTICAL       : strong statistical / causal / deep-dive analysis
  - LIGHT_ANALYTICAL : aggregations with grouping, summary/analysis keywords, or
                       information-seeking phrasing (user wants to KNOW, not just see)
  - VIZ_ONLY         : explicit chart/plot request without heavier analysis keywords
  - RETRIEVAL        : simple row lookup / count / direct data fetch
"""

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
    # "What is/are the X" — simple single-value lookups.
    # Safe to add back here because aggregation+grouping combos ("average X by Y")
    # are caught by _AGGREGATION_PATTERNS (checked before _RETRIEVAL_PATTERNS).
    re.compile(r"^\s*what\s+(?:is|are)\s+the\s+", re.I),
]

# Statistical / causal / deep-dive — always needs EDA + insight.
# Uses prefix stems (no closing \b on partial roots) so "correlation" matches
# "correlat", "trends" matches "trend", etc.
_STRONG_ANALYTICAL_PATTERNS: List[re.Pattern] = [
    re.compile(
        r"\b(?:why|how\s+come|reason|cause|driver|correlat\w*|trends?|forecast\w*|"
        r"predict\w*|distribution|outlier\w*|cluster\w*|segment\w*|"
        r"t[\s-]?test|chi[\s-]?square|anova|regression|hypothesis|"
        r"p[\s-]?value|significance|over\s+time|by\s+\w+\s+over)\b",
        re.I,
    ),
]

# Aggregation + grouping combos — needs sql + insight (no full EDA)
_AGGREGATION_PATTERNS: List[re.Pattern] = [
    re.compile(
        r"\b(average|avg|mean|median|std|variance|sum|total|count)\b.{0,40}"
        r"\b(by|per|each|group|category|department|region|segment|product|store|branch)\b",
        re.I | re.DOTALL,
    ),
    re.compile(r"\b(breakdown\s+(?:of|by)|grouped?\s+by)\b", re.I),
]

# Light analytical — analysis/insight/compare/summary keywords, no strong statistical signal
_LIGHT_ANALYTICAL_PATTERNS: List[re.Pattern] = [
    re.compile(
        r"\b(analy[sz]e|analysis|insight|compare|comparison|pattern|summary|summari[sz]e|report)\b",
        re.I,
    ),
]

# Explicit viz request
_VIZ_ONLY_PATTERNS: List[re.Pattern] = [
    re.compile(
        r"\b(plot|chart|visuali[sz]e|graph|histogram|scatter|heatmap|bar\s+chart|pie\s+chart|line\s+chart)\b",
        re.I,
    ),
]

# Information-seeking phrasing — user wants to KNOW something FROM the data, not
# just display it. Even when paired with "show"/"plot", these mean the answer
# requires interpretation (insight), not raw rows/charts alone.
# Kept deliberately narrow to avoid false-positives on filters/top-N lookups
# (e.g. "price more than 100", "which employees are in sales" stay RETRIEVAL).
_INFO_SEEKING_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bwhether\b", re.I),
    re.compile(
        r"\b(is|are)\s+there\s+(a|an|any)\s+"
        r"(difference|relationship|correlat\w*|pattern|trend|association|link|connection|gap|disparity)\b",
        re.I,
    ),
    re.compile(
        r"\b(difference|relationship|association|gap|disparity)\s+between\b",
        re.I,
    ),
    re.compile(
        r"\b(does|do|did|has|have)\b.{0,40}\b"
        r"(affect|affects|impact|impacts|influence|influences|differ|differs|relate|relates|"
        r"depend|depends|vary|varies|drive|drives|cause|causes)\b",
        re.I,
    ),
    re.compile(r"\b(impact|effect|influence)\s+of\b", re.I),
    re.compile(r"\bhow\s+(do|does|did)\b.{0,40}\b(compare|differ|relate|vary)\b", re.I),
]


def quick_classify(query: str) -> str:
    """Return ``"ANALYTICAL"``, ``"LIGHT_ANALYTICAL"``, ``"VIZ_ONLY"``, ``"RETRIEVAL"``, or ``""``."""
    if not query or len(query.strip()) < 3:
        return ""
    info_seeking = any(p.search(query) for p in _INFO_SEEKING_PATTERNS)
    # 1. Strong statistical / causal — always ANALYTICAL
    if any(p.search(query) for p in _STRONG_ANALYTICAL_PATTERNS):
        return "ANALYTICAL"
    # 2. Aggregation + grouping — LIGHT_ANALYTICAL
    if any(p.search(query) for p in _AGGREGATION_PATTERNS):
        return "LIGHT_ANALYTICAL"
    # 3. Explicit viz — VIZ_ONLY unless the user also wants to KNOW something.
    #    Info-seeking phrasing ("plot whether X differs") needs insight + chart.
    if any(p.search(query) for p in _VIZ_ONLY_PATTERNS):
        if info_seeking or any(p.search(query) for p in _LIGHT_ANALYTICAL_PATTERNS):
            return "LIGHT_ANALYTICAL"
        return "VIZ_ONLY"
    # 4. Information-seeking phrasing — user wants understanding, not raw rows.
    if info_seeking:
        return "LIGHT_ANALYTICAL"
    # 5. Summary / analysis / compare keywords — LIGHT_ANALYTICAL
    if any(p.search(query) for p in _LIGHT_ANALYTICAL_PATTERNS):
        return "LIGHT_ANALYTICAL"
    # 6. Clear retrieval signal
    if any(p.search(query) for p in _RETRIEVAL_PATTERNS):
        return "RETRIEVAL"
    return ""
