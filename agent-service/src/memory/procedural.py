"""Procedural memory (memory.md Phase 5): user-editable SQL/chart skill templates.

Stored in Qdrant so users add/edit/delete via the UI. Adapted from memory.md:
- vector size 768 (nomic-embed-text), not 1536
- embeddings via ``memory.embeddings.embed`` (one config path), not a per-class OpenAI client
- Qdrant point id IS the skill_id (a UUID string), so update/delete are direct lookups
  instead of memory.md's non-deterministic ``abs(hash(...))`` + scroll
- ``get_by_ids`` added so the planner can force-include skills the user picked with ``/``
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

logger = get_logger("memory.procedural")


_DEFAULT_SKILLS = [
    {
        "type": "sql",
        "name": "Revenue by dimension",
        "description": "Total revenue grouped by any single dimension (region, product, category)",
        "template": "SELECT {dimension}, SUM({revenue_col}) AS total_revenue FROM {table} WHERE {date_col} BETWEEN '{start}' AND '{end}' GROUP BY {dimension} ORDER BY total_revenue DESC",
    },
    {
        "type": "sql",
        "name": "Month-over-month growth",
        "description": "Month-over-month percentage growth for any metric",
        "template": "SELECT month, {metric}, ROUND(({metric} - LAG({metric}) OVER (ORDER BY month)) / LAG({metric}) OVER (ORDER BY month) * 100, 2) AS growth_pct FROM (SELECT DATE_TRUNC('month', {date_col}) AS month, SUM({metric_col}) AS {metric} FROM {table} GROUP BY 1) t",
    },
    {
        "type": "chart",
        "name": "Bar comparison chart",
        "description": "Compare values across categories — revenue by region, sales by product",
        "template": "import plotly.express as px\nfig = px.bar(df, x='{category_col}', y='{value_col}', title='{title}')\nfig.show()",
    },
    {
        "type": "chart",
        "name": "Time series line chart",
        "description": "Show trends over time — daily, monthly, yearly metrics",
        "template": "import plotly.express as px\nfig = px.line(df, x='{date_col}', y='{value_col}', title='{title}')\nfig.show()",
    },
]


class ProceduralMemory:
    COLLECTION = "procedural_memory"

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
        self._seed_defaults()

    # ── infra ────────────────────────────────────────────────────────────────
    def _ensure_collection(self) -> None:
        existing = [c.name for c in self.client.get_collections().collections]
        if self.COLLECTION not in existing:
            self.client.create_collection(
                collection_name=self.COLLECTION,
                vectors_config=VectorParams(size=EMBEDDING_DIMS, distance=Distance.COSINE),
            )

    def _embed(self, text: str) -> list[float]:
        return embeddings.embed(
            text, base_url=self._embed_base_url, model=self._embed_model
        )

    def _seed_defaults(self) -> None:
        if self.client.count(collection_name=self.COLLECTION).count > 0:
            return
        for d in _DEFAULT_SKILLS:
            self.add(d["name"], d["description"], d["template"], d["type"], is_default=True)
        logger.info("seeded %d default skills", len(_DEFAULT_SKILLS))

    # ── CRUD ─────────────────────────────────────────────────────────────────
    def add(
        self,
        name: str,
        description: str,
        template: str,
        skill_type: str = "sql",
        is_default: bool = False,
    ) -> str:
        skill_id = str(uuid.uuid4())
        self.client.upsert(
            collection_name=self.COLLECTION,
            points=[
                PointStruct(
                    id=skill_id,  # UUID string == Qdrant point id (direct lookups)
                    vector=self._embed(description),
                    payload={
                        "skill_id": skill_id,
                        "user_id": self.user_id,
                        "name": name,
                        "description": description,
                        "template": template,
                        "type": skill_type,
                        "is_default": is_default,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    },
                )
            ],
        )
        return skill_id

    def retrieve(self, query: str, top_k: int = 2, skill_type: str | None = None) -> list[dict]:
        query_filter = None
        if skill_type:
            query_filter = Filter(
                must=[FieldCondition(key="type", match=MatchValue(value=skill_type))]
            )
        results = self.client.search(
            collection_name=self.COLLECTION,
            query_vector=self._embed(query),
            limit=top_k,
            query_filter=query_filter,
        )
        return [r.payload for r in results]

    def get_by_ids(self, skill_ids: list[str]) -> list[dict]:
        """Fetch specific skills by id (planner force-include when user picks via /)."""
        if not skill_ids:
            return []
        points = self.client.retrieve(
            collection_name=self.COLLECTION, ids=skill_ids, with_payload=True
        )
        return [p.payload for p in points]

    def list_all(self) -> list[dict]:
        results, _ = self.client.scroll(collection_name=self.COLLECTION, limit=200)
        return [r.payload for r in results]

    def update(self, skill_id: str, name: str, description: str, template: str) -> None:
        existing = self.client.retrieve(
            collection_name=self.COLLECTION, ids=[skill_id], with_payload=True
        )
        if not existing:
            raise ValueError(f"Skill {skill_id} not found")
        payload = existing[0].payload
        self.client.upsert(
            collection_name=self.COLLECTION,
            points=[
                PointStruct(
                    id=skill_id,
                    vector=self._embed(description),
                    payload={
                        **payload,
                        "name": name,
                        "description": description,
                        "template": template,
                    },
                )
            ],
        )

    def delete(self, skill_id: str) -> None:
        self.client.delete(collection_name=self.COLLECTION, points_selector=[skill_id])
