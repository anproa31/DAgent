"""HTTP client for the Databao context-engine service (query-aware /enhance)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from config.settings import CONTEXT_ENGINE_URL


async def get_enhanced_context(
    context_summary: str,
    query: str,
    *,
    datasources: Optional[List[Dict[str, Any]]] = None,
    fallback: str = "",
) -> str:
    """Call ``POST /enhance`` to produce query-focused semantic context.

    ``context_summary`` should be the aggregated markdown from the app
    ``/internal/schema`` ``context`` field (built by ``POST /build`` during
    registration). If the service is unreachable, returns ``fallback`` (callers
    often pass the full combined schema markdown so prompts still have columns).
    """
    text = (context_summary or "").strip()
    if not text:
        return fallback

    payload: Dict[str, Any] = {"context_summary": text, "query": query or ""}
    if datasources:
        payload["datasources"] = datasources

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(f"{CONTEXT_ENGINE_URL}/enhance", json=payload)
            response.raise_for_status()
            data = response.json()
            out = data.get("enhanced_context", "")
            if isinstance(out, str) and out.strip():
                return out
    except Exception as exc:
        print(f"[context_engine] /enhance failed, using fallback: {exc}")

    return fallback
