"""Replay datasource DDL from the app service on sandbox startup."""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

import httpx

from api.schemas import RegisterDatasourceRequest
from datasources import registry, snippets
from infrastructure.config import DATASOURCE_SYNC_URL
from infrastructure.logging_setup import logger


async def bootstrap_from_app() -> None:
    url = f"{DATASOURCE_SYNC_URL}/internal/sandbox-bootstrap"
    data: Optional[Dict[str, Any]] = None
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            for attempt in range(8):
                try:
                    response = await client.get(url)
                    response.raise_for_status()
                    data = response.json()
                    break
                except Exception as exc:
                    logger.info("Datasource bootstrap retry %s: %s", attempt + 1, exc)
                    await asyncio.sleep(2.0)
            else:
                logger.warning(
                    "Skipping datasource bootstrap; app service unreachable at %s", url
                )
                return
    except Exception as exc:
        logger.warning("Datasource bootstrap failed: %s", exc)
        return

    if data is None:
        return

    sources = data.get("datasources", [])
    registered = 0
    failed = 0
    for source in sources:
        try:
            request = RegisterDatasourceRequest(**source)
        except Exception as exc:
            logger.warning("Skipping malformed datasource payload from app: %s", exc)
            failed += 1
            continue

        try:
            for snippet in request.sql_snippets:
                snippets.apply_snippet(snippet, request)
            registry.set_record(
                request.datasource_id,
                {
                    "name": request.name,
                    "type": request.type,
                    "view_names": list(request.view_names),
                    "config": dict(request.config),
                    "sql_snippets": list(request.sql_snippets),
                },
            )
            registered += 1
        except Exception as exc:
            logger.warning(
                "Failed to re-register datasource %s (%s): %s",
                request.name,
                request.datasource_id,
                exc,
            )
            failed += 1

    logger.info(
        "Datasource bootstrap: %d registered, %d failed (of %d reported)",
        registered,
        failed,
        len(sources),
    )
