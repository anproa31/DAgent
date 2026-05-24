"""Tests for procedural-memory default skills (memory.md Phase 5).

Service-free: validates the seed constant + the empty get_by_ids short-circuit without
constructing a Qdrant-backed instance.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memory.procedural import _DEFAULT_SKILLS, ProceduralMemory  # noqa: E402


def test_four_defaults_with_required_fields():
    assert len(_DEFAULT_SKILLS) == 4
    for skill in _DEFAULT_SKILLS:
        assert {"type", "name", "description", "template"} <= skill.keys()
        assert skill["type"] in {"sql", "chart"}
        assert skill["template"].strip()


def test_default_types_cover_sql_and_chart():
    types = {s["type"] for s in _DEFAULT_SKILLS}
    assert {"sql", "chart"} <= types


def test_get_by_ids_empty_short_circuits_without_client():
    # __new__ skips __init__ (no Qdrant connection); empty list returns [] before any client use.
    inst = ProceduralMemory.__new__(ProceduralMemory)
    assert inst.get_by_ids([]) == []
