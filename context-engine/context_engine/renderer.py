"""Markdown rendering for context summaries."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .classifier import ColumnContext
from .relationships import Relationship


def render_context_markdown(
    datasource_name: str,
    domain: str,
    domain_summary: str,
    table_grains: Dict[str, str],
    table_row_counts: Dict[str, Optional[int]],
    column_contexts: Dict[str, List[ColumnContext]],
    relationships: List[Relationship],
    capabilities: List[str],
    max_length: int = 2000,
) -> str:
    """Render a concise, LLM-friendly context summary as markdown."""
    lines: List[str] = []

    lines.append(f"## Datasource Context: {datasource_name} ({domain})")
    lines.append("")
    lines.append(domain_summary)
    lines.append("")

    # Tables section
    lines.append("### Tables")
    for tname, grain in table_grains.items():
        row_count = table_row_counts.get(tname)
        count_str = f" ({row_count:,} records)" if row_count else ""
        lines.append(f"- `{tname}` — {grain}{count_str}")

        cols = column_contexts.get(tname, [])
        for ctx in cols:
            desc = ctx.description or "Unspecified"
            role_str = ctx.role
            detail = f" — {ctx.detail}" if ctx.detail else ""
            lines.append(f"  - `{ctx.name}` ({role_str}): {desc}{detail}")
    lines.append("")

    # Relationships section
    if relationships:
        lines.append("### Relationships")
        for rel in relationships:
            if rel.confidence >= 0.9:
                lines.append(f"- `{rel.source_column}` links `{rel.source_table}` → `{rel.target_table}`")
            else:
                lines.append(f"- `{rel.source_column}` in `{rel.source_table}` may reference `{rel.target_table}`.{rel.target_column}")
        lines.append("")

    # Query capabilities section
    if capabilities:
        lines.append("### Query Capabilities")
        lines.append("This datasource can answer questions about:")
        for cap in capabilities:
            lines.append(f"- {cap}")
        lines.append("")

    result = "\n".join(lines).strip()
    if len(result) > max_length:
        # Truncate column details first, then capabilities
        result = _truncate_context(result, max_length)
    return result


def _truncate_context(text: str, max_length: int) -> str:
    """Truncate context text while preserving structure."""
    if len(text) <= max_length:
        return text

    lines = text.split("\n")
    result_lines: List[str] = []
    current_length = 0

    for line in lines:
        if current_length + len(line) + 1 <= max_length:
            result_lines.append(line)
            current_length += len(line) + 1
        else:
            break

    if len(result_lines) < len(lines):
        result_lines.append("...")

    return "\n".join(result_lines)


def render_enhanced_context(
    full_context: str,
    query: str,
) -> str:
    """Filter context to highlight only query-relevant portions.

    Uses keyword matching to find relevant table/column names in the query,
    then extracts those sections from the full context.
    """
    import re

    # Extract keywords from query (nouns, potential column/table names)
    query_lower = query.lower()

    # Split context into table sections
    sections = re.split(r"(?=### )", full_context)

    relevant_sections: List[str] = []
    for section in sections:
        section_lower = section.lower()
        # Check if any query keywords appear in this section
        # Look for backtick-quoted identifiers that match query words
        query_words = set(re.findall(r"\b\w+\b", query_lower))
        query_words -= {"the", "a", "an", "is", "are", "was", "were", "be", "been",
                        "what", "how", "why", "which", "when", "where", "who",
                        "show", "me", "give", "get", "list", "find", "tell",
                        "by", "in", "on", "at", "to", "for", "of", "and", "or",
                        "do", "does", "did", "can", "could", "would", "should",
                        "average", "total", "count", "sum", "max", "min",
                        "per", "each", "every", "all", "top", "bottom",
                        "first", "last", "most", "least"}

        if any(word in section_lower for word in query_words) or any(
            f"`{word}`" in section_lower for word in query_words
        ):
            relevant_sections.append(section)

    if relevant_sections:
        return "\n".join(relevant_sections).strip()

    # If no specific match, return the full context (shortened)
    return full_context[:1500] if len(full_context) > 1500 else full_context
