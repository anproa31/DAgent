"""Tests for the document ingestion pipeline (memory.md Phase 3).

Service-free: uses a stub SemanticMemory so no Qdrant/Ollama is required.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from memory.ingestion import (  # noqa: E402
    IngestionPipeline,
    extract_text_from_csv,
    extract_text_from_txt,
)


class _StubSemantic:
    """Collects chunks instead of embedding/storing them."""

    def __init__(self):
        self.chunks: list[tuple[str, str, int]] = []

    def store_chunk(self, chunk: str, source_filename: str, chunk_index: int):
        self.chunks.append((chunk, source_filename, chunk_index))


def test_extract_txt():
    assert extract_text_from_txt(b"hello world") == "hello world"


def test_extract_csv_summarizes():
    csv = b"a,b\n1,2\n3,4\n"
    out = extract_text_from_csv(csv)
    assert "Columns:" in out
    assert "Shape:" in out
    assert "1" in out and "4" in out


def test_pipeline_chunks_and_stores():
    sem = _StubSemantic()
    pipeline = IngestionPipeline(sem, chunk_size=50, chunk_overlap=10)
    text = ("sentence one. " * 40).encode("utf-8")
    result = pipeline.ingest(text, "doc.txt")

    assert result["filename"] == "doc.txt"
    assert result["chunks_stored"] > 1
    assert result["chunks_stored"] == len(sem.chunks)
    # chunk indices are sequential from 0
    assert [c[2] for c in sem.chunks] == list(range(len(sem.chunks)))
    assert all(c[1] == "doc.txt" for c in sem.chunks)


def test_unsupported_extension_raises():
    sem = _StubSemantic()
    pipeline = IngestionPipeline(sem)
    with pytest.raises(ValueError, match="Unsupported file type"):
        pipeline.ingest(b"data", "archive.zip")


def test_empty_text_raises():
    sem = _StubSemantic()
    pipeline = IngestionPipeline(sem)
    with pytest.raises(ValueError, match="Could not extract text"):
        pipeline.ingest(b"   ", "blank.txt")
