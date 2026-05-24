"""Document ingestion pipeline (memory.md Phase 3).

Accept an uploaded file (PDF/DOCX/CSV/TXT/MD), extract text, split into chunks, and store
each chunk in the ``semantic_user_kb`` collection. LangChain 1.x: the splitter lives in
``langchain_text_splitters``, not ``langchain.text_splitter``.
"""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter

from config.settings import CHUNK_OVERLAP, CHUNK_SIZE
from memory.semantic import SemanticMemory
from utils.agent_logger import get_logger

logger = get_logger("memory.ingestion")


# ── text extractors per file type ───────────────────────────────────────────
def extract_text_from_pdf(file_bytes: bytes) -> str:
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def extract_text_from_docx(file_bytes: bytes) -> str:
    import docx2txt

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as f:
            f.write(file_bytes)
            tmp_path = f.name
        return docx2txt.process(tmp_path)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def extract_text_from_csv(file_bytes: bytes) -> str:
    import pandas as pd

    df = pd.read_csv(io.BytesIO(file_bytes))
    summary = f"Columns: {list(df.columns)}\nShape: {df.shape}\n\n"
    return summary + df.head(20).to_string(index=False)


def extract_text_from_txt(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="ignore")


EXTRACTORS = {
    ".pdf": extract_text_from_pdf,
    ".docx": extract_text_from_docx,
    ".csv": extract_text_from_csv,
    ".txt": extract_text_from_txt,
    ".md": extract_text_from_txt,
}


class IngestionPipeline:
    def __init__(
        self,
        semantic_memory: SemanticMemory,
        chunk_size: int = CHUNK_SIZE,
        chunk_overlap: int = CHUNK_OVERLAP,
    ):
        self.sem = semantic_memory
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ".", " "],
        )

    def ingest(self, file_bytes: bytes, filename: str) -> dict:
        ext = Path(filename).suffix.lower()
        extractor = EXTRACTORS.get(ext)
        if not extractor:
            raise ValueError(
                f"Unsupported file type: {ext}. Supported: {list(EXTRACTORS.keys())}"
            )

        raw_text = extractor(file_bytes)
        if not raw_text.strip():
            raise ValueError(f"Could not extract text from {filename}")

        chunks = self.splitter.split_text(raw_text)
        for i, chunk in enumerate(chunks):
            self.sem.store_chunk(chunk=chunk, source_filename=filename, chunk_index=i)

        logger.info("ingested %s: %d chunks, %d chars", filename, len(chunks), len(raw_text))
        return {
            "filename": filename,
            "chunks_stored": len(chunks),
            "total_chars": len(raw_text),
        }
