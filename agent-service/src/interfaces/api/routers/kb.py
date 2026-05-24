"""Knowledge-base upload endpoints (memory.md Phase 7.2).

Mounted under ``/agent`` in main.py, so routes resolve to ``/agent/kb/*``. Embedding endpoint
+ model can be overridden per request (Settings UI); otherwise the server env default is used.
"""

from __future__ import annotations

from fastapi import APIRouter, File, HTTPException, UploadFile

from config.settings import MAX_UPLOAD_SIZE_MB, MEMORY_USER_ID
from memory.ingestion import IngestionPipeline
from memory.semantic import SemanticMemory

router = APIRouter(prefix="/kb", tags=["knowledge-base"])


def _semantic(user_id: str, embedding_base_url: str, embedding_model: str) -> SemanticMemory:
    return SemanticMemory(
        user_id=user_id or MEMORY_USER_ID,
        embedding_base_url=embedding_base_url or None,
        embedding_model=embedding_model or None,
    )


@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = MEMORY_USER_ID,
    embedding_base_url: str = "",
    embedding_model: str = "",
):
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_SIZE_MB}MB limit")

    sem = _semantic(user_id, embedding_base_url, embedding_model)
    pipeline = IngestionPipeline(sem)
    try:
        result = pipeline.ingest(file_bytes=contents, filename=file.filename)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "success", **result}


@router.get("/documents")
async def list_documents(
    user_id: str = MEMORY_USER_ID,
    embedding_base_url: str = "",
    embedding_model: str = "",
):
    sem = _semantic(user_id, embedding_base_url, embedding_model)
    return {"documents": sem.list_kb_documents()}


@router.delete("/documents/{filename}")
async def delete_document(
    filename: str,
    user_id: str = MEMORY_USER_ID,
    embedding_base_url: str = "",
    embedding_model: str = "",
):
    sem = _semantic(user_id, embedding_base_url, embedding_model)
    sem.delete_kb_document(filename)
    return {"status": "deleted", "filename": filename}
