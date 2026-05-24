"""Semantic memory (memory.md Phase 2): Mem0 + Qdrant.

Two collections:
- ``semantic_system``  : glossary / KPIs / preferences — written by code + consolidation
- ``semantic_user_kb`` : user-uploaded document chunks — written by the ingestion pipeline

Adapted from memory.md:
- 768-dim vectors (nomic-embed-text), not 1536
- Mem0 *embedder* uses the **openai** provider pointed at the Ollama-compatible ``/v1`` endpoint
  (same path as ``memory.embeddings``) so no extra ``ollama`` lib is needed and config stays
  in one place
- KB chunks are stored with ``infer=False`` so document text is kept verbatim and no chat LLM
  is required for ingestion
- ``retrieve`` accepts ``sources`` to scope KB recall to the documents the user picked with ``@``
"""

from __future__ import annotations

import os

from mem0 import Memory

from config.settings import (
    EMBEDDING_BASE_URL,
    EMBEDDING_DIMS,
    EMBEDDING_MODEL,
    MEMORY_LLM_MODEL,
    QDRANT_URL,
)
from utils.agent_logger import get_logger

logger = get_logger("memory.semantic")

_SYSTEM_COLLECTION = "semantic_system"
_USER_KB_COLLECTION = "semantic_user_kb"


def _qdrant_host_port(qdrant_url: str) -> tuple[str, int]:
    # Mem0's qdrant config takes host+port (not a full url) most reliably.
    cleaned = qdrant_url.replace("http://", "").replace("https://", "").rstrip("/")
    host, _, port = cleaned.partition(":")
    return host, int(port or 6333)


def _make_mem0_config(
    collection_name: str,
    qdrant_url: str,
    embedding_base_url: str,
    embedding_model: str,
) -> dict:
    host, port = _qdrant_host_port(qdrant_url)
    api_key = os.getenv("OPENAI_API_KEY", "ollama") or "ollama"
    return {
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "collection_name": collection_name,
                "host": host,
                "port": port,
                "embedding_model_dims": EMBEDDING_DIMS,
            },
        },
        "embedder": {
            "provider": "openai",
            "config": {
                "model": embedding_model,
                "embedding_dims": EMBEDDING_DIMS,
                "openai_base_url": embedding_base_url,
                "api_key": api_key,
            },
        },
        "llm": {
            "provider": "openai",
            "config": {
                "model": MEMORY_LLM_MODEL,
                "openai_base_url": os.getenv("OPENAI_BASE_URL") or embedding_base_url,
                "api_key": api_key,
            },
        },
    }


class SemanticMemory:
    def __init__(
        self,
        user_id: str,
        qdrant_url: str | None = None,
        *,
        embedding_base_url: str | None = None,
        embedding_model: str | None = None,
    ):
        self.user_id = user_id
        qdrant = qdrant_url or QDRANT_URL
        embed_url = embedding_base_url or EMBEDDING_BASE_URL
        embed_model = embedding_model or EMBEDDING_MODEL
        self.system = Memory.from_config(
            _make_mem0_config(_SYSTEM_COLLECTION, qdrant, embed_url, embed_model)
        )
        self.user_kb = Memory.from_config(
            _make_mem0_config(_USER_KB_COLLECTION, qdrant, embed_url, embed_model)
        )

    # ── writes ───────────────────────────────────────────────────────────────
    def store_fact(self, fact: str, category: str = "general") -> None:
        """Programmatic facts: glossary, KPIs, preferences (LLM inference on)."""
        self.system.add(
            messages=[{"role": "user", "content": fact}],
            user_id=self.user_id,
            metadata={"category": category},
        )

    def store_chunk(self, chunk: str, source_filename: str, chunk_index: int) -> None:
        """Store a verbatim document chunk (infer=False → no LLM, no rewriting)."""
        self.user_kb.add(
            messages=[{"role": "user", "content": chunk}],
            user_id=self.user_id,
            metadata={"source": source_filename, "chunk_index": chunk_index},
            infer=False,
        )

    # ── reads ────────────────────────────────────────────────────────────────
    def retrieve(
        self, query: str, top_k: int = 5, sources: list[str] | None = None
    ) -> list[dict]:
        """Merge system facts + KB chunks. ``sources`` scopes KB to picked documents."""
        combined: list[dict] = []
        user_filter = {"user_id": self.user_id}

        sys_results = self.system.search(query=query, filters=user_filter, top_k=top_k)
        for r in sys_results.get("results", []):
            combined.append({"text": r.get("memory", ""), "source": "system"})

        # Over-fetch then post-filter by source (robust across Mem0 filter dialects).
        kb_limit = top_k * 3 if sources else top_k
        kb_results = self.user_kb.search(query=query, filters=user_filter, top_k=kb_limit)
        kb_hits = []
        for r in kb_results.get("results", []):
            src = (r.get("metadata") or {}).get("source", "user_kb")
            if sources and src not in sources:
                continue
            kb_hits.append({"text": r.get("memory", ""), "source": src})
        combined.extend(kb_hits[:top_k])
        return combined

    def list_kb_documents(self) -> list[str]:
        all_memories = self.user_kb.get_all(filters={"user_id": self.user_id}, top_k=1000)
        docs = set()
        for m in all_memories.get("results", []):
            src = (m.get("metadata") or {}).get("source")
            if src:
                docs.add(src)
        return sorted(docs)

    # ── delete ───────────────────────────────────────────────────────────────
    def delete_kb_document(self, source_filename: str) -> None:
        """Delete all chunks of one uploaded file (post-filter for Mem0 compatibility)."""
        all_memories = self.user_kb.get_all(filters={"user_id": self.user_id}, top_k=1000)
        deleted = 0
        for m in all_memories.get("results", []):
            if (m.get("metadata") or {}).get("source") == source_filename:
                mem_id = m.get("id")
                if mem_id:
                    self.user_kb.delete(memory_id=mem_id)
                    deleted += 1
        logger.info("deleted %d chunks for %s", deleted, source_filename)
