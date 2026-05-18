"""Table grain detection — what each row represents."""
from __future__ import annotations

import re
from typing import Dict, List, Optional


# Map entity names from identifier columns
_ENTITY_NAMES = {
    "employee": "employee",
    "emp": "employee",
    "user": "user",
    "customer": "customer",
    "cust": "customer",
    "client": "client",
    "contact": "contact",
    "person": "person",
    "order": "order",
    "sale": "sale",
    "transaction": "transaction",
    "txn": "transaction",
    "product": "product",
    "item": "item",
    "sku": "product",
    "invoice": "invoice",
    "payment": "payment",
    "department": "department",
    "dept": "department",
    "team": "team",
    "project": "project",
    "task": "task",
    "ticket": "ticket",
    "issue": "issue",
    "ticket": "support ticket",
    "location": "location",
    "office": "office",
    "site": "site",
    "store": "store",
    "branch": "branch",
    "category": "category",
    "review": "review",
    "feedback": "feedback",
    "survey": "survey",
    "metric": "metric",
    "event": "event",
    "log": "log entry",
    "record": "record",
}


def _extract_entity_from_column(col_name: str) -> Optional[str]:
    """Extract entity name from an identifier column name."""
    base = re.sub(r"(?i)(_id|_key|_uuid)$", "", col_name)
    base = base.lower().strip("_")
    if base in _ENTITY_NAMES:
        return _ENTITY_NAMES[base]
    # Try partial match: 'employee_id' contains 'employee'
    for key, entity in _ENTITY_NAMES.items():
        if key in base or base in key:
            return entity
    return None


def _extract_entity_from_table(table_name: str) -> Optional[str]:
    """Extract entity name from a table/view name."""
    name = table_name.lower()
    # Remove common prefixes/suffixes
    name = re.sub(r"(?i)^(tbl_|dim_|fact_|stg_|raw_)", "", name)
    for key, entity in _ENTITY_NAMES.items():
        if key in name:
            return entity
    return None


def infer_table_grain(
    table_name: str,
    column_contexts: Dict[str, object],  # ColumnContext objects
    pk_candidates: Optional[List[str]] = None,
) -> str:
    """Infer what each row in the table represents.

    Returns a string like 'One row per employee'.
    """
    # Priority 1: PK candidate column
    if pk_candidates:
        for pk_col in pk_candidates:
            entity = _extract_entity_from_column(pk_col)
            if entity:
                return f"One row per {entity}"

    # Priority 2: Any identifier column
    for col_name, ctx in column_contexts.items():
        role = getattr(ctx, "role", "")
        is_pk = getattr(ctx, "is_primary_key_candidate", False)
        if role in ("identifier",) or is_pk:
            entity = _extract_entity_from_column(col_name)
            if entity:
                return f"One row per {entity}"

    # Priority 3: Foreign key → "One row per X record"
    for col_name, ctx in column_contexts.items():
        role = getattr(ctx, "role", "")
        if role == "foreign_key":
            entity = _extract_entity_from_column(col_name)
            if entity:
                return f"One row per {entity} record"

    # Priority 4: Table name inference
    entity = _extract_entity_from_table(table_name)
    if entity:
        return f"One row per {entity}"

    # Fallback
    return f"Records related to {table_name}"
