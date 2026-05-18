import uuid
from fastapi import APIRouter, HTTPException
from models.requests import CreateSessionRequest
from models.responses import CreateSessionResponse, SessionRunsResponse, SessionRunSummary

router = APIRouter()

# Simple in-memory session registry (maps session_id → metadata)
sessions: dict = {}


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(_: CreateSessionRequest = CreateSessionRequest()):
    """Create a new analytics session (equivalent to a 'space')."""
    session_id = str(uuid.uuid4())
    sessions[session_id] = {"runs": []}
    return CreateSessionResponse(session_id=session_id)


@router.get("/sessions/{session_id}/runs", response_model=SessionRunsResponse)
async def list_session_runs(session_id: str):
    """List all run IDs belonging to a session."""
    from routers.runs import _run_states

    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    runs = []
    for run_id in session.get("runs", []):
        run_state = _run_states.get(run_id)
        if run_state:
            runs.append(SessionRunSummary(
                run_id=run_id,
                query=run_state.query,
                done=run_state.done,
                error=run_state.error or None,
            ))
    return SessionRunsResponse(session_id=session_id, runs=runs)


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    sessions.pop(session_id, None)
    return {"success": True}
