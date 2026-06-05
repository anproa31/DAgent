"""Query-aware semantic context via databao-context-engine vector search."""
from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional

from databao_context_engine import DatabaoContextEngine, DatasourceId

from config.settings import DCE_DOMAIN_DIR, DCE_SEARCH_LIMIT
from context.dce_integration import get_domain_manager, patch_dce_ollama

logger = logging.getLogger(__name__)

_DCE_CONFIG_PREFIX = "daa"


@lru_cache
def _get_context_engine(domain_dir: str) -> DatabaoContextEngine:
    patch_dce_ollama()
    get_domain_manager(domain_dir)
    return DatabaoContextEngine(domain_dir=Path(domain_dir))


def _registry_ids_from_datasources(datasources: Optional[List[Dict[str, Any]]]) -> List[DatasourceId]:
    if not datasources:
        return []
    ids: List[DatasourceId] = []
    for ds in datasources:
        registry_id = ds.get("id")
        if not registry_id:
            continue
        ids.append(DatasourceId.from_string_repr(f"{_DCE_CONFIG_PREFIX}/{registry_id}.yaml"))
    return ids


def _search_context_sync(
    query: str,
    *,
    datasources: Optional[List[Dict[str, Any]]] = None,
    limit: int,
) -> str:
    engine = _get_context_engine(DCE_DOMAIN_DIR)
    datasource_ids = _registry_ids_from_datasources(datasources)
    results = engine.search_context(
        query,
        limit=limit,
        datasource_ids=datasource_ids or None,
    )
    if not results:
        return ""
    return "\n\n".join(result.context_result.strip() for result in results if result.context_result.strip())


async def get_enhanced_context(
    context_summary: str,
    query: str,
    *,
    datasources: Optional[List[Dict[str, Any]]] = None,
    fallback: str = "",
) -> str:
    """Return query-focused semantic context from DCE hybrid search.

    ``context_summary`` is kept for API compatibility (built during datasource
    registration). When search returns nothing, falls back to ``context_summary``
    or the caller-provided ``fallback``.
    """
    text = (query or "").strip()
    if not text:
        return (context_summary or "").strip() or fallback

    try:
        enhanced = await asyncio.to_thread(
            _search_context_sync,
            text,
            datasources=datasources,
            limit=DCE_SEARCH_LIMIT,
        )
        if enhanced.strip():
            return enhanced
    except Exception as exc:
        logger.warning("DCE search_context failed, using fallback: %s", exc)

    return (context_summary or "").strip() or fallback
