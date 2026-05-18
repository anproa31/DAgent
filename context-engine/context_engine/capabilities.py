"""Query capability generation from domain + column analysis."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .classifier import ColumnRole, ColumnContext

# Capability templates: (required_role_or_pattern, capability_string)
_CAPABILITY_TEMPLATES: List[tuple] = [
    # HR domain
    (lambda cols, domain: "hr" in domain and any(c.role == ColumnRole.MEASURE and "salary" in c.name.lower() for c in cols),
     "Salary distribution and analysis"),
    (lambda cols, domain: "hr" in domain and any("hire" in c.name.lower() or "date" in c.name.lower() for c in cols),
     "Tenure and hiring trends"),
    (lambda cols, domain: "hr" in domain and any("attrition" in c.name.lower() or "churn" in c.name.lower() or "termination" in c.name.lower() for c in cols),
     "Attrition patterns and trends"),
    (lambda cols, domain: "hr" in domain and any(c.role == ColumnRole.DIMENSION and "department" in c.name.lower() for c in cols),
     "Department composition and structure"),
    (lambda cols, domain: "hr" in domain and any(c.role == ColumnRole.DIMENSION and c.name.lower() in ("gender", "sex") for c in cols),
     "Demographic diversity analysis"),

    # Sales domain
    (lambda cols, domain: "sale" in domain and any("revenue" in c.name.lower() or "amount" in c.name.lower() for c in cols),
     "Revenue trends and analysis"),
    (lambda cols, domain: "sale" in domain and any("order" in c.name.lower() or "sale" in c.name.lower() for c in cols),
     "Order volume and patterns"),
    (lambda cols, domain: "sale" in domain and any("customer" in c.name.lower() or "client" in c.name.lower() for c in cols),
     "Customer analysis and segmentation"),
    (lambda cols, domain: "sale" in domain and any("product" in c.name.lower() or "item" in c.name.lower() for c in cols),
     "Product performance analysis"),

    # Finance domain
    (lambda cols, domain: "finance" in domain and any("expense" in c.name.lower() or "cost" in c.name.lower() for c in cols),
     "Expense tracking and analysis"),
    (lambda cols, domain: "finance" in domain and any("budget" in c.name.lower() for c in cols),
     "Budget vs actual comparison"),
    (lambda cols, domain: "finance" in domain and any("tax" in c.name.lower() for c in cols),
     "Tax liability analysis"),

    # General temporal capabilities
    (lambda cols, domain: any(c.role == ColumnRole.TEMPORAL for c in cols),
     "Time-based trend analysis"),

    # General measure capabilities
    (lambda cols, domain: any(c.role == ColumnRole.MEASURE for c in cols),
     "Aggregation and statistical analysis"),

    # Multi-table join capability
    (lambda cols, domain: False, None),  # handled separately in engine
]


def generate_capabilities(
    domain: str,
    table_column_contexts: Dict[str, List[ColumnContext]],
    has_relationships: bool = False,
) -> List[str]:
    """Generate a list of natural language query capabilities."""
    caps = set()

    for check_fn, cap_str in _CAPABILITY_TEMPLATES:
        if cap_str is None:
            continue
        # Flatten all column contexts across tables
        all_cols = []
        for cols in table_column_contexts.values():
            all_cols.extend(cols)
        if all_cols and check_fn(all_cols, domain.lower()):
            caps.add(cap_str)

    # Add join capability if relationships exist
    if has_relationships and len(table_column_contexts) > 1:
        table_names = list(table_column_contexts.keys())
        caps.add(f"Cross-table analysis: {' + '.join(table_names[:3])}")

    if not caps:
        # Fallback: generic capability
        caps.add("Data retrieval and exploration")

    return sorted(caps)
