"""Tests for the planner↔memory bridge (build_memory_context).

Service-free: the MemoryManager factory is monkeypatched, so no Qdrant/Redis/Ollama needed.
Verifies the guard rails (empty inputs, backend failure) and selection passthrough.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import memory.manager as manager_mod  # noqa: E402
from agents.planner.memory_context import build_memory_context  # noqa: E402


def test_returns_empty_without_session_or_query():
    assert build_memory_context({"query": "x"}) == ""
    assert build_memory_context({"session_id": "s"}) == ""


def test_returns_empty_when_backend_unavailable(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("qdrant down")

    monkeypatch.setattr(manager_mod, "get_memory_manager", boom)
    out = build_memory_context({"session_id": "s1", "query": "revenue"})
    assert out == ""


def test_passes_selection_to_manager(monkeypatch):
    captured = {}

    class _FakeMgr:
        def build_prompt_context(self, query, kb_documents=None, skill_ids=None):
            captured["query"] = query
            captured["kb"] = kb_documents
            captured["skills"] = skill_ids
            return "## From your knowledge base\n[sales.pdf] revenue is net of returns"

    monkeypatch.setattr(manager_mod, "get_memory_manager", lambda *a, **k: _FakeMgr())

    state = {
        "session_id": "s1",
        "query": "what is revenue",
        "kb_documents": ["sales.pdf"],
        "skill_ids": ["abc"],
        "embedding_base_url": "http://localhost:11434/v1",
        "embedding_model": "nomic-embed-text",
    }
    out = build_memory_context(state)

    assert "knowledge base" in out
    assert captured["query"] == "what is revenue"
    assert captured["kb"] == ["sales.pdf"]
    assert captured["skills"] == ["abc"]
