"""Context engine orchestrator — builds and enhances context."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .classifier import ColumnContext, build_column_context_map
from .domain import generate_domain_summary, infer_domain
from .grain import infer_table_grain
from .relationships import Relationship, detect_relationships
from .capabilities import generate_capabilities
from .renderer import render_context_markdown, render_enhanced_context


class DatasourceContext:
    """Internal representation of enriched datasource context."""

    def __init__(self):
        self.datasource_name = ""
        self.domain = ""
        self.domain_summary = ""
        self.table_grains: Dict[str, str] = {}
        self.table_row_counts: Dict[str, Optional[int]] = {}
        self.column_contexts: Dict[str, List[ColumnContext]] = {}
        self.relationships: List[Relationship] = []
        self.capabilities: List[str] = []
        self.context_markdown = ""


def build_context(datasource_name: str, tables: List[Dict[str, Any]]) -> DatasourceContext:
    """Build semantic context from raw introspection data.

    tables: list of dicts with keys: name, columns, row_count, samples, column_stats
            columns: list of dicts with keys: name, type, nullable
    """
    ctx = DatasourceContext()
    ctx.datasource_name = datasource_name

    table_names = [t["name"] for t in tables]
    all_column_names = []

    # Build column contexts for each table
    for t in tables:
        tname = t["name"]
        columns = t.get("columns", [])
        row_count = t.get("row_count")
        raw_stats = t.get("column_stats", {})

        # Normalize stats: ColumnStats objects may be dicts
        stats = {}
        for col_name, s in raw_stats.items():
            if isinstance(s, dict):
                stats[col_name] = {
                    "distinct_count": s.get("distinct_count"),
                    "null_count": s.get("null_count"),
                    "min_value": s.get("min_value"),
                    "max_value": s.get("max_value"),
                    "values": s.get("top_values"),
                    "_row_count": row_count,
                }

        col_ctx = build_column_context_map(columns, stats, row_count, table_names)
        ctx.column_contexts[tname] = list(col_ctx.values())
        all_column_names.extend(c["name"] for c in columns)

        # Table grain
        pk_candidates = [
            name for name, cctx in col_ctx.items()
            if cctx.is_primary_key_candidate
        ]
        ctx.table_grains[tname] = infer_table_grain(tname, col_ctx, pk_candidates or None)
        ctx.table_row_counts[tname] = row_count

    # Business domain
    domain, _matched = infer_domain(table_names, all_column_names)
    ctx.domain = domain

    # Domain summary — extract key features from column roles
    key_features = []
    for tname, cols in ctx.column_contexts.items():
        measures = [c for c in cols if c.role == "measure"]
        dimensions = [c for c in cols if c.role == "dimension"]
        if measures:
            key_features.append(f"{len(measures)} numeric measure(s)")
        if dimensions:
            key_features.append(f"{len(dimensions)} categorical dimension(s)")
        break  # Keep summary concise

    ctx.domain_summary = generate_domain_summary(domain, table_names, key_features[:3])

    # Relationships
    table_dicts = [{"name": t["name"], "columns": t["columns"]} for t in tables]
    ctx.relationships = detect_relationships(table_dicts, ctx.column_contexts)

    # Query capabilities
    ctx.capabilities = generate_capabilities(
        domain,
        ctx.column_contexts,
        has_relationships=len(ctx.relationships) > 0,
    )

    # Render markdown
    ctx.context_markdown = render_context_markdown(
        datasource_name=datasource_name,
        domain=domain,
        domain_summary=ctx.domain_summary,
        table_grains=ctx.table_grains,
        table_row_counts=ctx.table_row_counts,
        column_contexts=ctx.column_contexts,
        relationships=ctx.relationships,
        capabilities=ctx.capabilities,
    )

    return ctx


def enhance_for_query(context_summary: str, query: str) -> str:
    """Filter and enhance context for a specific user query."""
    return render_enhanced_context(context_summary, query)
