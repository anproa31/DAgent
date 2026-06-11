"""Episodic memory (memory.md Phase 4): Qdrant store of past session summaries.

Each episode records what was analyzed and the outcome; retrieved by semantic similarity to
the current query. 768-dim vectors (nomic-embed-text); embeddings via ``memory.embeddings``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from config.settings import EMBEDDING_DIMS, QDRANT_URL
from memory import embeddings
from utils.agent_logger import get_logger

logger = get_logger("memory.episodic")


class EpisodicMemory:
    COLLECTION = "episodic_memory"

    def __init__(
        self,
        user_id: str,
        qdrant_url: str | None = None,
        *,
        embedding_base_url: str | None = None,
        embedding_model: str | None = None,
    ):
        self.user_id = user_id
        self._embed_base_url = embedding_base_url
        self._embed_model = embedding_model
        self.client = QdrantClient(url=qdrant_url or QDRANT_URL)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        existing = [c.name for c in self.client.get_collections().collections]
        if self.COLLECTION not in existing:
            self.client.create_collection(
                collection_name=self.COLLECTION,
                vectors_config=VectorParams(size=EMBEDDING_DIMS, distance=Distance.COSINE),
            )

    def _embed(self, text: str) -> list[float]:
        return embeddings.embed(text, base_url=self._embed_base_url, model=self._embed_model)

    def store_episode(self, summary: str, metadata: dict | None = None) -> str:
        episode_id = str(uuid.uuid4())
        self.client.upsert(
            collection_name=self.COLLECTION,
            points=[
                PointStruct(
                    id=episode_id,
                    vector=self._embed(summary),
                    payload={
                        "episode_id": episode_id,
                        "user_id": self.user_id,
                        "summary": summary,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        **(metadata or {}),
                    },
                )
            ],
        )
        logger.info("stored episode %s", episode_id)
        return episode_id

    def retrieve_similar(self, query: str, top_k: int = 3) -> list[dict]:
        results = self.client.query_points(
            collection_name=self.COLLECTION,
            query=self._embed(query),
            limit=top_k,
            query_filter=Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=self.user_id))]
            ),
        ).points
        return [r.payload for r in results]
