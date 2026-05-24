"""Background consolidation (memory.md Phase 6).

At run/session end, distil the working-memory snapshot into:
- an episode summary  → episodic memory
- new durable facts   → semantic (system) memory

Uses the existing OpenAI-compatible ``llm_client`` (no second client config). Best-effort:
any failure is logged and swallowed so consolidation never breaks the run.
"""

from __future__ import annotations

import json
from typing import Any

from config.settings import MEMORY_LLM_MODEL
from memory.episodic import EpisodicMemory
from memory.semantic import SemanticMemory
from utils.agent_logger import get_logger
from utils.llm_client import chat_complete, get_async_client

logger = get_logger("memory.consolidator")

_SYSTEM_PROMPT = (
    "You consolidate a data-analysis session into long-term memory. "
    "Given the session snapshot, reply with STRICT JSON: "
    '{"episode_summary": "<=3 sentence summary of dataset, what was asked, what was found>", '
    '"facts": ["durable reusable fact 1", "..."]}. '
    "Facts must be general domain/glossary/preference knowledge worth recalling in future "
    "sessions — not run-specific chatter. Return [] if none."
)


class Consolidator:
    def __init__(self, episodic: EpisodicMemory, semantic: SemanticMemory, model: str | None = None):
        self.episodic = episodic
        self.semantic = semantic
        self.model = model or MEMORY_LLM_MODEL

    async def run(self, session_id: str, session_snapshot: dict[str, Any]) -> dict[str, Any]:
        if not session_snapshot or not any(session_snapshot.values()):
            return {"episode_summary": None, "facts_stored": 0}

        try:
            client = get_async_client()
            content = await chat_complete(
                client,
                self.model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(session_snapshot)[:6000]},
                ],
                temperature=0.1,
                log_tag="consolidator",
            )
            parsed = _safe_json(content)
        except Exception as e:  # pragma: no cover - network/LLM failure is non-fatal
            logger.warning("consolidation LLM failed for %s: %s", session_id, e)
            return {"episode_summary": None, "facts_stored": 0}

        summary = (parsed.get("episode_summary") or "").strip()
        facts = [f for f in (parsed.get("facts") or []) if isinstance(f, str) and f.strip()]

        if summary:
            try:
                self.episodic.store_episode(summary, metadata={"session_id": session_id})
            except Exception as e:  # pragma: no cover
                logger.warning("store_episode failed: %s", e)

        stored = 0
        for fact in facts:
            try:
                self.semantic.store_fact(fact, category="consolidated")
                stored += 1
            except Exception as e:  # pragma: no cover
                logger.warning("store_fact failed: %s", e)

        return {"episode_summary": summary or None, "facts_stored": stored}


def _safe_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:]
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}
