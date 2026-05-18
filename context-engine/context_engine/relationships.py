"""Cross-table relationship detection."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class Relationship:
    source_table: str
    source_column: str
    target_table: str
    target_column: str
    confidence: float  # 0.0–1.0
    description: str


def _strip_id_suffix(col_name: str) -> str:
    """Remove _id/_key suffix to get the base entity name."""
    return re.sub(r"(?i)(_id|_key)$", "", col_name).lower()


def detect_relationships(
    tables: List[Dict],
    column_contexts: Dict[str, Dict[str, object]],
) -> List[Relationship]:
    """Detect relationships between tables based on column name analysis.

    tables: list of dicts with 'name' and 'columns' keys
    column_contexts: {table_name: {col_name: ColumnContext}}
    """
    relationships: List[Relationship] = []
    table_names = [t["name"] for t in tables]

    # Build a map: table_name → set of column names (lowercase)
    col_map: Dict[str, Dict[str, str]] = {}  # table_name → {lower_col: original_col}
    for t in tables:
        col_map[t["name"]] = {c["name"].lower(): c["name"] for c in t["columns"]}

    # Strategy 1: Exact same column name across tables (confidence 1.0)
    col_to_tables: Dict[str, List[str]] = {}
    for tname, cols in col_map.items():
        for lcol, ocol in cols.items():
            col_to_tables.setdefault(lcol, []).append(tname)

    for col, tnames in col_to_tables.items():
        if len(tnames) >= 2:
            # Skip if it's a generic column like 'name' or 'id'
            if col in ("name", "id", "description", "created_at", "updated_at"):
                continue
            for i in range(len(tnames)):
                for j in range(i + 1, len(tnames)):
                    relationships.append(Relationship(
                        source_table=tnames[i],
                        source_column=col_map[tnames[i]].get(col, col),
                        target_table=tnames[j],
                        target_column=col_map[tnames[j]].get(col, col),
                        confidence=1.0,
                        description=f"Shared column '{col}'",
                    ))

    # Strategy 2: FK pattern — column_X_id in table A likely references table X
    for t in tables:
        tname = t["name"]
        for col in t["columns"]:
            base = _strip_id_suffix(col["name"].lower())
            if base == col["name"].lower():
                continue  # No suffix, skip

            # Look for a table whose name contains this base
            for other in table_names:
                if other == tname:
                    continue
                if base in other.lower() or other.lower() in base:
                    # Check if target table has an 'id' or matching column
                    other_cols = set(col_map[other].keys())
                    target_col = None
                    if f"{base}_id" in other_cols or "id" in other_cols:
                        target_col = col_map[other].get(f"{base}_id", "id")
                    elif col["name"].lower() in other_cols:
                        target_col = col_map[other][col["name"].lower()]

                    if target_col:
                        # Avoid duplicating exact-match relationships
                        already_exists = any(
                            r.source_table == tname and r.source_column == col["name"]
                            and r.target_table == other
                            for r in relationships
                        )
                        if not already_exists:
                            relationships.append(Relationship(
                                source_table=tname,
                                source_column=col["name"],
                                target_table=other,
                                target_column=target_col,
                                confidence=0.8,
                                description=f"Foreign key: {col['name']} → {other}.{target_col}",
                            ))

    return relationships
