"""MemoryManager (memory.md Phase 9): wires all memory layers.

``build_prompt_context`` merges working + semantic (system facts + KB) + episodic + procedural
into one prompt block, source-tagged. Optional ``kb_documents`` / ``skill_ids`` scope retrieval
to what the user picked in the composer (``@`` / ``/``).

Every layer read is wrapped defensively: a memory backend being down must never break the
agent run — it just contributes nothing to the context.

Managers are cached per (user_id, session_id, embedding config) because constructing Mem0 /
Qdrant clients is not free and the planner calls ``build_prompt_context`` on every step.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from config.settings import MEMORY_USER_ID
from memory.consolidator import Consolidator
from memory.episodic import EpisodicMemory
from memory.procedural import ProceduralMemory
from memory.semantic import SemanticMemory
from memory.working import WorkingMemory
from utils.agent_logger import get_logger

logger = get_logger("memory.manager")


class MemoryManager:
    def __init__(
        self,
        user_id: str,
        session_id: str,
        *,
        embedding_base_url: str | None = None,
        embedding_model: str | None = None,
    ):
        self.user_id = user_id
        self.session_id = session_id
        self.working = WorkingMemory(session_id)
        self.semantic = SemanticMemory(
            user_id, embedding_base_url=embedding_base_url, embedding_model=embedding_model
        )
        self.episodic = EpisodicMemory(
            user_id, embedding_base_url=embedding_base_url, embedding_model=embedding_model
        )
        self.procedural = ProceduralMemory(
            user_id, embedding_base_url=embedding_base_url, embedding_model=embedding_model
        )
        self._consolidator = Consolidator(self.episodic, self.semantic)

    def build_prompt_context(
        self,
        user_query: str,
        kb_documents: list[str] | None = None,
        skill_ids: list[str] | None = None,
    ) -> str:
        ctx: list[str] = []

        wm = _safe(lambda: self.working.get_context_snapshot(), {}, "working")
        if wm.get("dataset_schema"):
            ctx.append(f"## Active dataset\n{wm['dataset_schema']}")
        if wm.get("tool_outputs"):
            ctx.append(f"## Recent tool outputs\n{wm['tool_outputs'][-3:]}")

        sem_results = _safe(
            lambda: self.semantic.retrieve(user_query, top_k=5, sources=kb_documents or None),
            [],
            "semantic",
        )
        if sem_results:
            sys_facts = [r for r in sem_results if r["source"] == "system"]
            kb_chunks = [r for r in sem_results if r["source"] != "system"]
            if sys_facts:
                ctx.append(
                    "## Domain knowledge\n" + "\n".join(f"- {r['text']}" for r in sys_facts)
                )
            if kb_chunks:
                ctx.append(
                    "## From your knowledge base\n"
                    + "\n".join(f"[{r['source']}] {r['text']}" for r in kb_chunks)
                )

        past = _safe(lambda: self.episodic.retrieve_similar(user_query, top_k=3), [], "episodic")
        if past:
            ctx.append(
                "## Related past sessions\n" + "\n".join(f"- {s.get('summary', '')}" for s in past)
            )

        if skill_ids:
            procedures = _safe(lambda: self.procedural.get_by_ids(skill_ids), [], "procedural")
        else:
            procedures = _safe(lambda: self.procedural.retrieve(user_query, top_k=2), [], "procedural")
        if procedures:
            ctx.append(
                "## Relevant templates\n"
                + "\n".join(
                    f"- [{p.get('name')}] {p.get('description')}\n  {p.get('template')}"
                    for p in procedures
                )
            )

        return "\n\n".join(ctx)

    async def end_session(
        self,
        *,
        llm_model: str = "",
        llm_base_url: str = "",
        llm_api_key: str = "",
    ) -> dict[str, Any]:
        snapshot = _safe(lambda: self.working.clear(), {}, "working.clear")
        return await self._consolidator.run(
            session_id=self.session_id,
            session_snapshot=snapshot,
            llm_model=llm_model,
            llm_base_url=llm_base_url,
            llm_api_key=llm_api_key,
        )


def _safe(fn, default, tag):
    try:
        return fn()
    except Exception as e:  # pragma: no cover - memory backend down must not break the agent
        logger.warning("memory layer '%s' unavailable: %s", tag, e)
        return default


@lru_cache(maxsize=64)
def _cached_manager(
    user_id: str, session_id: str, embedding_base_url: str, embedding_model: str
) -> MemoryManager:
    return MemoryManager(
        user_id,
        session_id,
        embedding_base_url=embedding_base_url or None,
        embedding_model=embedding_model or None,
    )


def get_memory_manager(
    session_id: str,
    *,
    user_id: str | None = None,
    embedding_base_url: str = "",
    embedding_model: str = "",
) -> MemoryManager:
    """Cached MemoryManager factory (planner calls this every step)."""
    return _cached_manager(
        user_id or MEMORY_USER_ID, session_id, embedding_base_url, embedding_model
    )
