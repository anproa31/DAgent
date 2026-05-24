"""Shared embedding helper for the memory system.

Replaces memory.md's per-class ``from openai import OpenAI`` with a single config path.
Uses the OpenAI-compatible ``/v1/embeddings`` endpoint, which Ollama exposes, so the local
``nomic-embed-text`` model (768-dim) works without any extra client library.

The endpoint + model are user-configurable from the frontend Settings dialog and passed
per request; ``config.settings`` values are the server-side fallback. Clients are cached per
(base_url, api_key) so repeated calls reuse one connection pool.
"""

from __future__ import annotations

import os
from functools import lru_cache

from openai import OpenAI

from config.settings import EMBEDDING_BASE_URL, EMBEDDING_MODEL


@lru_cache(maxsize=8)
def _client(base_url: str, api_key: str) -> OpenAI:
    return OpenAI(base_url=base_url, api_key=api_key or "ollama")


def _resolve(base_url: str | None, model: str | None) -> tuple[str, str]:
    return (base_url or EMBEDDING_BASE_URL, model or EMBEDDING_MODEL)


def embed(text: str, *, base_url: str | None = None, model: str | None = None) -> list[float]:
    """Embed a single string. Returns a 768-dim vector for nomic-embed-text."""
    url, mdl = _resolve(base_url, model)
    client = _client(url, os.getenv("OPENAI_API_KEY", "ollama"))
    res = client.embeddings.create(model=mdl, input=text)
    return res.data[0].embedding


def embed_batch(
    texts: list[str], *, base_url: str | None = None, model: str | None = None
) -> list[list[float]]:
    """Embed many strings in one request (used by ingestion for throughput)."""
    if not texts:
        return []
    url, mdl = _resolve(base_url, model)
    client = _client(url, os.getenv("OPENAI_API_KEY", "ollama"))
    res = client.embeddings.create(model=mdl, input=texts)
    # OpenAI guarantees response order matches input order.
    return [d.embedding for d in res.data]
