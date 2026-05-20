"""HTTP client for the context-engine microservice."""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from ...core.config import Settings, get_settings
from ...dce_introspection import IntrospectionOutcome

logger = logging.getLogger(__name__)


class ContextEngineClient:
    """Builds semantic context summaries for datasource schemas."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()

    async def build_context(self, datasource_name: str, outcome: IntrospectionOutcome) -> str:
        """Return context summary markdown, or empty string on failure."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self._settings.context_engine_url.rstrip("/") + "/build",
                    json={
                        "datasource_name": datasource_name,
                        "tables": [
                            {
                                "name": tbl.name,
                                "columns": [
                                    {"name": c, "type": t, "nullable": n}
                                    for c, t, n in tbl.columns
                                ],
                                "row_count": tbl.row_count,
                                "samples": tbl.samples,
                                "column_stats": {
                                    cn: {
                                        "distinct_count": cs.distinct_count,
                                        "null_count": cs.null_count,
                                        "min_value": cs.min_value,
                                        "max_value": cs.max_value,
                                        "top_values": cs.top_values,
                                    }
                                    for cn, cs in tbl.column_stats.items()
                                },
                            }
                            for tbl in outcome.tables
                        ],
                    },
                )
                response.raise_for_status()
                return response.json().get("context_summary", "")
        except Exception as exc:
            logger.warning("Context-engine unavailable, skipping context build: %s", exc)
            return ""
