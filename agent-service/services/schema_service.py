"""Schema retrieval client for the agent service.

The app service exposes two endpoints:

- ``/internal/schema`` — markdown blocks keyed by DuckDB view name.
- ``/internal/datasources`` — structured datasource list with kind/type.

The orchestrator uses the structured list to decide between SQL- and
Python-first pipelines (e.g. a CSV is naturally tabular, a PDF is not).
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx

APP_SERVICE_URL = os.getenv("APP_SERVICE_URL", "http://app:8000").rstrip("/")


def combined_markdown_from_payload(data: Dict[str, Any], tables: Optional[List[str]] = None) -> str:
    """Pick the best schema markdown string from a ``/internal/schema`` JSON body."""
    combined = data.get("combined")
    if isinstance(combined, str) and combined.strip():
        return combined

    schema_parts = data.get("schema", {})
    if isinstance(schema_parts, dict):
        if tables:
            filtered = {k: v for k, v in schema_parts.items() if k in tables}
            blocks = filtered.values() if filtered else schema_parts.values()
        else:
            blocks = schema_parts.values()
        seen: set[str] = set()
        unique_blocks: List[str] = []
        for block in blocks:
            if block and block not in seen:
                seen.add(block)
                unique_blocks.append(block)
        return "\n\n".join(unique_blocks) if unique_blocks else "No schema registered"
    return str(schema_parts)


async def fetch_schema_payload(tables: Optional[List[str]] = None) -> Dict[str, Any]:
    """Return the parsed JSON from ``GET /internal/schema`` (empty dict on failure)."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            params: Dict[str, str] = {}
            if tables:
                params["tables"] = ",".join(tables)
            response = await client.get(f"{APP_SERVICE_URL}/internal/schema", params=params)
            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, dict) else {}
    except Exception as exc:
        print(f"[schema_service] Failed to fetch schema payload: {exc}")
        return {}


async def get_schema(tables: Optional[List[str]] = None) -> str:
    """Fetch schema markdown from the app's internal endpoint.

    Prefer the pre-rendered ``combined`` block when available — it folds
    in cross-datasource join hints that the per-view dict cannot express.
    Falls back to per-view de-duplication for older app versions.
    """
    data = await fetch_schema_payload(tables)
    if not data:
        return "Schema unavailable"
    return combined_markdown_from_payload(data, tables)


async def get_datasources() -> List[Dict[str, Any]]:
    """Return the structured datasource list (kind/type/views)."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(f"{APP_SERVICE_URL}/internal/datasources")
            response.raise_for_status()
            data = response.json()
            return list(data.get("datasources", []))
    except Exception as exc:
        print(f"[schema_service] Failed to fetch datasources: {exc}")
        return []
