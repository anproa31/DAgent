"""LLM-assisted web dataset discovery and registration."""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import openai

from ...models.datasource import DatasourceRecord
from .web_fetch_service import fetch_url_to_file
from .web_search_service import SearchResult, search_datasets
from .web_security import domain_trust_score, looks_like_data_file, validate_fetch_url

logger = logging.getLogger(__name__)


@dataclass
class DiscoverCandidate:
    title: str
    url: str
    snippet: str
    score: int
    reason: str = ""


@dataclass
class WebDiscoverOutcome:
    query: str
    candidates: List[DiscoverCandidate] = field(default_factory=list)
    selected_urls: List[str] = field(default_factory=list)
    datasources: List[DatasourceRecord] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    search_count: int = 0


def _heuristic_score(result: SearchResult) -> DiscoverCandidate:
    host = result.url.split("/")[2] if "://" in result.url else ""
    trust = domain_trust_score(host)
    score = trust
    if looks_like_data_file(result.url):
        score += 30
    text = f"{result.title} {result.snippet}".lower()
    for word in ("csv", "dataset", "download", "open data", "statistics", "official"):
        if word in text:
            score += 5
    return DiscoverCandidate(
        title=result.title,
        url=result.url,
        snippet=result.snippet,
        score=score,
        reason="heuristic ranking",
    )


async def _llm_rank_candidates(
    query: str,
    candidates: List[DiscoverCandidate],
    *,
    model: str,
    base_url: str,
    api_key: str,
    max_select: int,
) -> List[str]:
    if not candidates:
        return []

    catalog = [
        {
            "url": c.url,
            "title": c.title,
            "snippet": c.snippet[:300],
            "trust_score": c.score,
        }
        for c in candidates[:12]
    ]
    system = (
        "You help analysts find trustworthy downloadable datasets on the public web. "
        "Prefer official government, international organization, and established open-data sources. "
        "Select URLs that likely point directly to CSV, JSON, Parquet, or Excel files — "
        "not HTML dashboards, login pages, or news articles. "
        f"Return at most {max_select} URLs as JSON: "
        '{"selected":[{"url":"...","reason":"..."}]}'
    )
    user = f"User data need:\n{query}\n\nSearch results:\n{json.dumps(catalog, ensure_ascii=False)}"

    normalized = base_url.rstrip("/")
    if not normalized.endswith("/v1"):
        normalized = normalized.replace("/v1/", "").replace("/v1", "") + "/v1"

    client = openai.AsyncOpenAI(base_url=normalized, api_key=api_key or "none")
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
    )
    raw = response.choices[0].message.content or ""
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return []

    try:
        payload = json.loads(match.group())
    except json.JSONDecodeError:
        return []

    selected: List[str] = []
    for item in payload.get("selected", []):
        url = item.get("url", "").strip()
        if url and validate_fetch_url(url).ok:
            selected.append(url)
        if len(selected) >= max_select:
            break
    return selected


class WebDiscoverService:
    """Search → rank → fetch → register pipeline."""

    def __init__(
        self,
        registry: Any,
        *,
        max_search_results: int = 10,
        max_fetch_attempts: int = 3,
        max_bytes: int = 50 * 1024 * 1024,
        fetch_timeout: float = 30.0,
        allow_untrusted: bool = False,
    ) -> None:
        self._registry = registry
        self._max_search_results = max_search_results
        self._max_fetch_attempts = max_fetch_attempts
        self._max_bytes = max_bytes
        self._fetch_timeout = fetch_timeout
        self._allow_untrusted = allow_untrusted

    async def propose(
        self,
        query: str,
        *,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        direct_url: Optional[str] = None,
        max_fetch_attempts: Optional[int] = None,
    ) -> WebDiscoverOutcome:
        """Search and rank candidate URLs without downloading or registering."""
        fetch_limit = max_fetch_attempts or self._max_fetch_attempts
        outcome = WebDiscoverOutcome(query=query)

        if direct_url:
            validation = validate_fetch_url(direct_url, allow_untrusted=self._allow_untrusted)
            if not validation.ok:
                outcome.errors.append(validation.reason or "URL not allowed")
                return outcome
            outcome.selected_urls = [direct_url]
            outcome.candidates = [
                DiscoverCandidate(
                    title=direct_url,
                    url=direct_url,
                    snippet="Direct URL provided",
                    score=validation.trust_score,
                    reason="direct url",
                )
            ]
            return outcome

        search_results = await search_datasets(query, max_results=self._max_search_results)
        outcome.search_count = len(search_results)
        outcome.candidates = [_heuristic_score(r) for r in search_results]
        outcome.candidates.sort(key=lambda c: c.score, reverse=True)

        selected_urls: List[str] = []
        if model and base_url and outcome.candidates:
            try:
                selected_urls = await _llm_rank_candidates(
                    query,
                    outcome.candidates,
                    model=model,
                    base_url=base_url,
                    api_key=api_key or "",
                    max_select=fetch_limit,
                )
                for url in selected_urls:
                    for cand in outcome.candidates:
                        if cand.url == url:
                            cand.reason = "llm selected"
            except Exception as exc:
                logger.warning("LLM ranking failed, using heuristics: %s", exc)
                outcome.errors.append(f"LLM ranking failed: {exc}")

        if not selected_urls:
            selected_urls = [
                c.url
                for c in outcome.candidates
                if validate_fetch_url(c.url, allow_untrusted=self._allow_untrusted).ok
            ][:fetch_limit]

        outcome.selected_urls = selected_urls
        if not selected_urls:
            outcome.errors.append("No trustworthy downloadable dataset URLs were found.")
        return outcome

    async def register_urls(
        self,
        urls: List[str],
        *,
        name: Optional[str] = None,
        query: str = "",
    ) -> WebDiscoverOutcome:
        """Fetch and register an explicit list of approved URLs."""
        outcome = WebDiscoverOutcome(query=query or "web import")
        outcome.selected_urls = list(urls)
        ds_name = name or _name_from_query(query or "web_dataset")

        for idx, url in enumerate(urls):
            suffix = f"_{idx + 1}" if idx else ""
            record = await self._try_register_url(url, name=f"{ds_name}{suffix}")
            if record:
                outcome.datasources.append(record)
            else:
                outcome.errors.append(f"Fetch/register failed: {url}")
        return outcome

    async def discover_and_register(
        self,
        query: str,
        *,
        name: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        direct_url: Optional[str] = None,
        max_fetch_attempts: Optional[int] = None,
    ) -> WebDiscoverOutcome:
        fetch_limit = max_fetch_attempts or self._max_fetch_attempts
        proposal = await self.propose(
            query,
            model=model,
            base_url=base_url,
            api_key=api_key,
            direct_url=direct_url,
            max_fetch_attempts=fetch_limit,
        )
        if not proposal.selected_urls:
            return proposal

        return await self.register_urls(
            proposal.selected_urls,
            name=name,
            query=query,
        )

    async def _try_register_url(self, url: str, *, name: str) -> Optional[DatasourceRecord]:
        try:
            fetched, _validation = await fetch_url_to_file(
                url,
                max_bytes=self._max_bytes,
                timeout=self._fetch_timeout,
                allow_untrusted=self._allow_untrusted,
            )
            return await self._registry.add_fetched_file_datasource(
                name=name,
                stored_path=fetched.stored_path,
                original_filename=fetched.original_filename,
                file_type=fetched.file_type,
                source_url=fetched.source_url,
            )
        except Exception as exc:
            logger.warning("register from url failed %s: %s", url, exc)
            return None


def _name_from_query(query: str) -> str:
    text = re.sub(r"[^\w\s-]", "", query.lower())
    text = re.sub(r"\s+", "_", text.strip())
    return (text[:48] or "web_dataset").strip("_")
