"""HTTP client for app-service web datasource discovery."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx

from config.settings import APP_SERVICE_URL
from utils.agent_logger import get_logger

logger = get_logger("web_datasource_client")


async def _post_json(path: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(f"{APP_SERVICE_URL}{path}", json=payload)
        response.raise_for_status()
        return response.json()


async def propose_web_data(
    query: str,
    *,
    url: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    max_results: int = 3,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"query": query, "max_results": max_results}
    if url:
        payload["url"] = url
    if model:
        payload["model"] = model
    if base_url:
        payload["base_url"] = base_url
    if api_key:
        payload["api_key"] = api_key

    logger.info("propose_web_data query=%r url=%s", query[:120], url or "(search)")
    try:
        return await _post_json("/internal/web/propose", payload, timeout=120.0)
    except Exception as exc:
        logger.error("propose_web_data failed: %s", exc)
        return {"errors": [str(exc)], "selected_urls": [], "candidates": [], "query": query}


async def register_web_data(
    urls: List[str],
    *,
    name: Optional[str] = None,
    query: Optional[str] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"urls": urls}
    if name:
        payload["name"] = name
    if query:
        payload["query"] = query

    logger.info("register_web_data urls=%d", len(urls))
    try:
        return await _post_json("/internal/web/register", payload, timeout=120.0)
    except Exception as exc:
        logger.error("register_web_data failed: %s", exc)
        return {"errors": [str(exc)], "datasources": [], "selected_urls": urls}


async def discover_web_data(
    query: str,
    *,
    url: Optional[str] = None,
    name: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    max_results: int = 3,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"query": query, "max_results": max_results}
    if url:
        payload["url"] = url
    if name:
        payload["name"] = name
    if model:
        payload["model"] = model
    if base_url:
        payload["base_url"] = base_url
    if api_key:
        payload["api_key"] = api_key

    try:
        return await _post_json("/internal/web/discover", payload, timeout=120.0)
    except Exception as exc:
        logger.error("discover_web_data failed: %s", exc)
        return {"errors": [str(exc)], "datasources": [], "query": query}


async def fetch_web_url(url: str, *, name: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"url": url}
    if name:
        payload["name"] = name

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                f"{APP_SERVICE_URL}/api/datasources/fetch-url",
                json=payload,
            )
            response.raise_for_status()
            record = response.json()
            return {"datasources": [record], "selected_urls": [url], "errors": []}
    except Exception as exc:
        logger.error("fetch_web_url failed: %s", exc)
        return {"errors": [str(exc)], "datasources": [], "selected_urls": [url]}


def summarize_discover_response(response: Dict[str, Any]) -> str:
    datasources: List[Dict[str, Any]] = response.get("datasources") or []
    if datasources:
        parts = []
        for ds in datasources:
            views = ", ".join(ds.get("view_names") or [])
            parts.append(f"- {ds.get('name')} ({ds.get('type')}): views [{views}]")
        return "Registered datasource(s) from the web:\n" + "\n".join(parts)

    selected = response.get("selected_urls") or []
    if selected:
        return "Proposed dataset URL(s):\n" + "\n".join(f"- {u}" for u in selected)

    errors = response.get("errors") or ["No datasets found"]
    return "Web discovery failed: " + "; ".join(errors)
