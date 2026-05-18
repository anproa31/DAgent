import uuid
from fastapi import APIRouter, HTTPException

from database import async_session_maker
from models.requests import CreateSessionRequest
from models.responses import (
    CreateSessionResponse,
    SessionRunsResponse,
    SessionRunSummary,
    SessionListResponse,
    SessionListItem,
    SessionDetailResponse,
)
from repositories import run_repository, session_repository
from run_registry import RUN_STATES

router = APIRouter()


def _merge_run_summary(
    row,
    live,
) -> SessionRunSummary:
    if live:
        return SessionRunSummary(
            run_id=row.run_id,
            query=live.query,
            done=live.done,
            error=live.error or None,
        )
    return SessionRunSummary(
        run_id=row.run_id,
        query=row.query,
        done=row.done,
        error=row.error or None,
    )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions():
    async with async_session_maker() as db:
        rows = await session_repository.list_sessions(db)
        return SessionListResponse(
            sessions=[
                SessionListItem(
                    session_id=r.id,
                    title=r.title or "Analysis",
                    updated_at=r.updated_at,
                )
                for r in rows
            ]
        )


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(body: CreateSessionRequest = CreateSessionRequest()):
    session_id = str(uuid.uuid4())
    title = (body.title or "").strip()
    async with async_session_maker() as db:
        await session_repository.create_session(db, session_id, title=title)
    return CreateSessionResponse(session_id=session_id)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session_detail(session_id: str):
    async with async_session_maker() as db:
        sess = await session_repository.get_session_with_runs(db, session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
        summaries = []
        for row in sess.runs:
            live = RUN_STATES.get(row.run_id)
            summaries.append(_merge_run_summary(row, live))
        return SessionDetailResponse(
            session_id=sess.id,
            title=sess.title or "Analysis",
            runs=summaries,
        )


@router.get("/sessions/{session_id}/runs", response_model=SessionRunsResponse)
async def list_session_runs(session_id: str):
    async with async_session_maker() as db:
        sess = await session_repository.get_session(db, session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
        rows = await run_repository.get_session_runs(db, session_id)

    runs = [_merge_run_summary(row, RUN_STATES.get(row.run_id)) for row in rows]
    return SessionRunsResponse(session_id=session_id, runs=runs)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    async with async_session_maker() as db:
        rows = await run_repository.get_session_runs(db, session_id)
        for r in rows:
            RUN_STATES.pop(r.run_id, None)
        deleted = await session_repository.delete_session(db, session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"success": True}
