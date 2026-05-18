"""Column semantic classification via name-pattern and type heuristics."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class ColumnRole:
    IDENTIFIER = "identifier"
    FOREIGN_KEY = "foreign_key"
    DIMENSION = "dimension"
    TEMPORAL = "temporal"
    MEASURE = "measure"
    TEXT = "text"


# Human-readable descriptions for each role
_ROLE_DESCRIPTIONS = {
    ColumnRole.IDENTIFIER: "Unique identifier",
    ColumnRole.FOREIGN_KEY: "Foreign key reference",
    ColumnRole.DIMENSION: "Categorical grouping",
    ColumnRole.TEMPORAL: "Date/time value",
    ColumnRole.MEASURE: "Numeric metric",
    ColumnRole.TEXT: "Free text",
}

# Name-pattern rules: (regex, role, human description).
# Ordered by specificity — more specific patterns first.
_IDENTIFIER_PATTERNS = [
    (r"(?i)^\w*_id$", ColumnRole.IDENTIFIER, "Unique identifier"),
    (r"(?i)^\w*_key$", ColumnRole.IDENTIFIER, "Unique key"),
    (r"(?i)^(id|uuid|code|number|no|num|sku|isbn|isbn13)$", ColumnRole.IDENTIFIER, "Unique identifier"),
]

_FOREIGN_KEY_PATTERNS = [
    (r"(?i)^\w+_(id|key)$", ColumnRole.FOREIGN_KEY, "Reference to related entity"),
]

_DIMENSION_PATTERNS = [
    (r"(?i)\b(department|dept|division|unit|team|group|org)\b", ColumnRole.DIMENSION, "Organizational grouping"),
    (r"(?i)\b(city|state|country|region|province|zip|postal)\b", ColumnRole.DIMENSION, "Geographic location"),
    (r"(?i)\b(status|type|category|class|level|tier|grade|stage|phase)\b", ColumnRole.DIMENSION, "Classification category"),
    (r"(?i)\b(gender|sex|race|ethnicity|marital)\b", ColumnRole.DIMENSION, "Demographic category"),
    (r"(?i)\b(attrition|churn|retained|active|enabled|disabled|flag|is_)\b", ColumnRole.DIMENSION, "Status flag"),
    (r"(?i)\b(role|title|position|job|function)\b", ColumnRole.DIMENSION, "Role or position"),
    (r"(?i)\b(mode|method|channel|source|medium)\b", ColumnRole.DIMENSION, "Process category"),
    (r"(?i)\b(currency|unit|measure|language|locale)\b", ColumnRole.DIMENSION, "Unit of measure"),
    (r"(?i)\b(priority|severity|rating|score|rank)\b", ColumnRole.DIMENSION, "Rating or rank"),
    (r"(?i)\b(color|brand|model|variant|version)\b", ColumnRole.DIMENSION, "Product attribute"),
]

_TEMPORAL_PATTERNS = [
    (r"(?i)(date|time|timestamp|datetime|year|month|quarter|week|day|hour|minute)\b", ColumnRole.TEMPORAL, "Date or time value"),
    (r"(?i)\b(created|updated|modified|deleted|started|ended|completed|resolved|closed|opened|published|expired)\b", ColumnRole.TEMPORAL, "Event timestamp"),
    (r"(?i)\b(fiscal|period|season|semester)\b", ColumnRole.TEMPORAL, "Time period"),
    (r"(?i)\b(age|tenure|duration|years?_?of|months?_?of)\b", ColumnRole.TEMPORAL, "Duration value"),
]

_MEASURE_PATTERNS = [
    (r"(?i)\b(salary|wage|pay|income|revenue|profit|cost|price|fee|tax|discount|bonus|commission)\b", ColumnRole.MEASURE, "Financial amount"),
    (r"(?i)\b(amount|total|sum|quantity|count|volume|weight|height|size|length|area)\b", ColumnRole.MEASURE, "Numeric quantity"),
    (r"(?i)\b(rate|ratio|percentage|percent|pct|avg|mean|median)\b", ColumnRole.MEASURE, "Rate or percentage"),
    (r"(?i)\b(score|rating|points|index)\b", ColumnRole.MEASURE, "Numeric score"),
    (r"(?i)\b(age|years|months|days)\b", ColumnRole.MEASURE, "Numeric duration"),
    (r"(?i)\b(lat|latitude|lon|longitude|elevation)\b", ColumnRole.MEASURE, "Geographic coordinate"),
]

_TEXT_PATTERNS = [
    (r"(?i)\b(name|first[_ ]?name|last[_ ]?name|full[_ ]?name|middle[_ ]?name)\b", ColumnRole.TEXT, "Person name"),
    (r"(?i)\b(description|comment|note|remark|summary|detail|reason|explanation)\b", ColumnRole.TEXT, "Descriptive text"),
    (r"(?i)\b(address|street|city_name|state_name|country_name)\b", ColumnRole.TEXT, "Address text"),
    (r"(?i)\b(email|phone|mobile|fax|url|website|link)\b", ColumnRole.TEXT, "Contact information"),
    (r"(?i)\b(content|body|message|text|label|tag)\b", ColumnRole.TEXT, "Content text"),
]


def _is_numeric_type(type_str: str) -> bool:
    upper = type_str.upper()
    return any(tok in upper for tok in ("INT", "DECIMAL", "DOUBLE", "FLOAT", "REAL", "NUMERIC", "BIGINT", "SMALLINT", "SERIAL"))


def _is_temporal_type(type_str: str) -> bool:
    upper = type_str.upper()
    return any(tok in upper for tok in ("DATE", "TIME", "TIMESTAMP", "INTERVAL"))


def _is_string_type(type_str: str) -> bool:
    upper = type_str.upper()
    return any(tok in upper for tok in ("VARCHAR", "CHAR", "TEXT", "STRING", "NVARCHAR"))


def _match_patterns(name: str, patterns: list) -> Optional[tuple]:
    """Return first matching pattern or None."""
    for regex, role, desc in patterns:
        if re.search(regex, name):
            return (role, desc)
    return None


@dataclass
class ColumnContext:
    name: str
    role: str = ColumnRole.TEXT
    description: str = "Unspecified column"
    is_primary_key_candidate: bool = False
    is_foreign_key_candidate: bool = False
    semantic_label: str = ""
    detail: str = ""


def classify_column(
    name: str,
    type_str: str,
    stats: Optional[Dict[str, Any]] = None,
    all_table_names: Optional[List[str]] = None,
) -> ColumnContext:
    """Classify a column's semantic role using name patterns, type, and stats."""
    ctx = ColumnContext(name=name)

    # Stage 1: Name-pattern matching (primary signal)
    fk_match = _match_patterns(name, _FOREIGN_KEY_PATTERNS)
    id_match = _match_patterns(name, _IDENTIFIER_PATTERNS)

    # Check if an ID column is actually a foreign key
    if id_match and all_table_names:
        base = re.sub(r"(?i)(_id|_key)$", "", name)
        for tbl in all_table_names:
            if base.lower() in tbl.lower() and tbl.lower() != name.lower():
                ctx.role = ColumnRole.FOREIGN_KEY
                ctx.description = f"Reference to {base}"
                ctx.is_foreign_key_candidate = True
                break
        else:
            ctx.role = ColumnRole.IDENTIFIER
            ctx.description = id_match[1]
            ctx.is_primary_key_candidate = True
    elif fk_match:
        ctx.role = ColumnRole.FOREIGN_KEY
        ctx.description = fk_match[1]
        ctx.is_foreign_key_candidate = True
    elif id_match:
        ctx.role = ColumnRole.IDENTIFIER
        ctx.description = id_match[1]
        ctx.is_primary_key_candidate = True
    else:
        # Try domain-specific patterns
        for pattern_list in [_DIMENSION_PATTERNS, _TEMPORAL_PATTERNS, _MEASURE_PATTERNS, _TEXT_PATTERNS]:
            match = _match_patterns(name, pattern_list)
            if match:
                ctx.role = match[0]
                ctx.description = match[1]
                break

    # Stage 2: Type confirmation
    if ctx.role == ColumnRole.MEASURE and not _is_numeric_type(type_str):
        # If name suggests measure but type is string, downgrade
        if _is_string_type(type_str):
            ctx.role = ColumnRole.DIMENSION if ctx.role == ColumnRole.MEASURE else ctx.role
            ctx.description = "Text value"

    # Stage 3: Stats confirmation
    if stats:
        distinct = stats.get("distinct_count")
        nulls = stats.get("null_count", 0)
        row_count = stats.get("_row_count")  # injected by caller

        if distinct is not None and row_count and distinct == row_count and nulls == 0:
            if ctx.role == ColumnRole.IDENTIFIER or ctx.role == ColumnRole.FOREIGN_KEY:
                ctx.is_primary_key_candidate = True
                if not ctx.description or ctx.description == "Unspecified column":
                    ctx.description = "Unique identifier, primary key candidate"

        if distinct is not None and distinct <= 25 and ctx.role not in (ColumnRole.IDENTIFIER, ColumnRole.FOREIGN_KEY, ColumnRole.TEMPORAL, ColumnRole.MEASURE):
            ctx.role = ColumnRole.DIMENSION
            if "values" in stats and stats["values"]:
                preview = ", ".join(str(v) for v in stats["values"][:8])
                ctx.detail = f"[values: {preview}]"

        if ctx.role == ColumnRole.MEASURE:
            if stats.get("min_value") is not None and stats.get("max_value") is not None:
                ctx.detail = f"range: {stats['min_value']} → {stats['max_value']}"

    # Fallback: type-based classification
    if ctx.role == ColumnRole.TEXT and ctx.description == "Unspecified column":
        if _is_numeric_type(type_str):
            ctx.role = ColumnRole.MEASURE
            ctx.description = "Numeric value"
        elif _is_temporal_type(type_str):
            ctx.role = ColumnRole.TEMPORAL
            ctx.description = "Date or time value"

    # Build semantic label
    role_label = _ROLE_DESCRIPTIONS.get(ctx.role, "")
    name_parts = re.sub(r"[_\-]", " ", name)
    ctx.semantic_label = name_parts.title().strip()

    return ctx


def build_column_context_map(
    columns: List[Dict[str, Any]],
    stats: Dict[str, Dict[str, Any]],
    row_count: Optional[int] = None,
    all_table_names: Optional[List[str]] = None,
) -> Dict[str, ColumnContext]:
    """Build context for all columns in a table."""
    result = {}
    for col in columns:
        col_name = col["name"]
        col_type = col["type"]
        col_stats = stats.get(col_name, {})
        if row_count is not None:
            col_stats["_row_count"] = row_count
        result[col_name] = classify_column(col_name, col_type, col_stats, all_table_names)
    return result
