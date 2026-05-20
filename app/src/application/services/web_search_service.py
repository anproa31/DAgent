"""Lightweight web search for dataset discovery (DuckDuckGo Lite, no API key)."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from html import unescape
from typing import List
from urllib.parse import parse_qs, unquote, urlparse

import httpx

logger = logging.getLogger(__name__)

_USER_AGENT = (
    "Mozilla/5.0 (compatible; DataAnalystAgent/1.0; +https://github.com/databao)"
)


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


def _unwrap_ddg_redirect(href: str) -> str:
    if "uddg=" in href:
        parsed = urlparse(href)
        params = parse_qs(parsed.query)
        uddg = params.get("uddg", [""])[0]
        if uddg:
            return unquote(uddg)
    return href


def _parse_ddg_lite(html: str, max_results: int) -> List[SearchResult]:
    results: List[SearchResult] = []
    # Rows: <a rel="nofollow" href="...">Title</a> ... snippet in next td
    link_pattern = re.compile(
        r'<a[^>]+class="result-link"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    snippet_pattern = re.compile(
        r'<td[^>]+class="result-snippet"[^>]*>(.*?)</td>',
        re.IGNORECASE | re.DOTALL,
    )

    links = link_pattern.findall(html)
    snippets = snippet_pattern.findall(html)

    for idx, (href, title_html) in enumerate(links[:max_results]):
        title = re.sub(r"<[^>]+>", "", unescape(title_html)).strip()
        url = _unwrap_ddg_redirect(unescape(href).strip())
        snippet = ""
        if idx < len(snippets):
            snippet = re.sub(r"<[^>]+>", "", unescape(snippets[idx])).strip()
        if url.startswith("http"):
            results.append(SearchResult(title=title, url=url, snippet=snippet))
    return results


async def search_datasets(
    query: str,
    *,
    max_results: int = 8,
    timeout: float = 20.0,
) -> List[SearchResult]:
    """Search the web for datasets related to *query*."""
    search_query = f"{query} dataset csv OR parquet open data download"
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.post(
                "https://lite.duckduckgo.com/lite/",
                data={"q": search_query},
                headers={"User-Agent": _USER_AGENT},
            )
            response.raise_for_status()
    except Exception as exc:
        logger.warning("web search failed for %r: %s", query, exc)
        return []

    return _parse_ddg_lite(response.text, max_results=max_results)
