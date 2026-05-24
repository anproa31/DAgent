"""Bridge the memory system into the planner prompt.

Kept separate from ``context_builder`` (a pure, unit-tested function) because this reaches out
to Qdrant / Redis / Ollama. Every failure is swallowed: if the memory backend is down the
planner simply gets no memory block — the run continues unaffected.
"""

from __future__ import annotations

from agents.shared.state import AgentState
from config.settings import MEMORY_USER_ID
from utils.agent_logger import get_logger

logger = get_logger("planner.memory")


def build_memory_context(state: AgentState) -> str:
    """Return a prompt block with KB chunks / skills / past sessions, or '' on any failure."""
    session_id = state.get("session_id") or ""
    query = state.get("query") or ""
    if not session_id or not query:
        return ""

    try:
        from memory.manager import get_memory_manager

        mgr = get_memory_manager(
            session_id,
            user_id=MEMORY_USER_ID,
            embedding_base_url=state.get("embedding_base_url", "") or "",
            embedding_model=state.get("embedding_model", "") or "",
        )
        return mgr.build_prompt_context(
            query,
            kb_documents=state.get("kb_documents") or None,
            skill_ids=state.get("skill_ids") or None,
        )
    except Exception as e:  # pragma: no cover - memory is best-effort
        logger.warning("memory context unavailable: %s", e)
        return ""
