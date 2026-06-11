import asyncio
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from agents.orchestrator.reflection.memory import get_rl_memory
from infrastructure.database.connection import async_session_maker
from infrastructure.repositories import run_repository, session_repository
from interfaces.dto.requests import ApproveRequest, RejectRequest, StartRunRequest
from interfaces.dto.responses import (
    ApproveResponse,
    RejectResponse,
    RunReportResponse,
    StartRunResponse,
)
from orchestration.state_management.run_registry import RUN_STATES
from orchestration.workflows.graph import compiled_graph
from orchestration.workflows.run_executor import (
    RunState,
    build_initial_state,
    persist_run_to_db,
    run_graph,
    sse_event_generator,
)
from utils.sql_sanitize import clean_sql_for_execution

router = APIRouter()


@router.post("/sessions/{session_id}/runs", response_model=StartRunResponse)
async def start_run(session_id: str, body: StartRunRequest):
    run_id = str(uuid.uuid4())

    async with async_session_maker() as db:
        sess = await session_repository.get_session(db, session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
        await run_repository.create_run(db, run_id, session_id, body.query)
        await session_repository.touch_session(db, session_id)

    run = RunState(session_id=session_id, run_id=run_id, query=body.query)
    RUN_STATES[run_id] = run

    initial_input = build_initial_state(
        session_id=session_id,
        run_id=run_id,
        query=body.query,
        tables=body.tables,
        model=body.model,
        base_url=body.base_url,
        api_key=body.api_key,
        kb_documents=body.kb_documents,
        skill_ids=body.skill_ids,
        embedding_base_url=body.embedding_base_url,
        embedding_model=body.embedding_model,
    )

    asyncio.create_task(run_graph(run, initial_input))
    return StartRunResponse(run_id=run_id)


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    run = RUN_STATES.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return StreamingResponse(
        sse_event_generator(run),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/runs/{run_id}/approve", response_model=ApproveResponse)
async def approve_run(run_id: str, body: ApproveRequest):
    run = RUN_STATES.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.pending_approval_type == "python_review":
        code = body.code or run.python_code or ""
        run.approval_data = {"approved": True, "type": "python_review", "code": code}
        run.python_code = code
    else:
        sql = clean_sql_for_execution(body.sql or run.sql_draft or "")
        run.approval_data = {"approved": True, "sql": sql, "type": "sql_review"}
        run.sql_draft = sql

    run.approval_event.set()
    return ApproveResponse(success=True)


@router.post("/runs/{run_id}/reject", response_model=RejectResponse)
async def reject_run(run_id: str, body: RejectRequest):
    run = RUN_STATES.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.pending_approval_type == "python_review":
        run.approval_data = {
            "approved": False,
            "type": "python_review",
            "reason": body.reason,
            "code": body.code or run.python_code or "",
        }
    else:
        edited_sql = clean_sql_for_execution(body.sql if body.sql else run.sql_draft or "")
        run.approval_data = {"approved": False, "reason": body.reason, "sql": edited_sql}
        run.sql_draft = edited_sql
        run.sql_rejection_reason = body.reason

    run.approval_event.set()
    return RejectResponse(success=True)


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: str):
    run = RUN_STATES.get(run_id)
    if not run:
        return {"success": True, "already_stopped": True}

    run.done = True
    run.error = "stopped"
    run.completion_reason = "user_cancelled"
    if run.approval_event.is_set():
        run.approval_event.clear()
    run.approval_data = {"approved": False, "reason": "User stopped the run"}
    run.approval_event.set()

    try:
        await persist_run_to_db(run)
    except Exception as pe:
        print(f"[runs] stop persist error for run {run_id}: {pe}")

    return {"success": True, "already_stopped": False}


@router.get("/runs/{run_id}/report", response_model=RunReportResponse)
async def get_report(run_id: str):
    run = RUN_STATES.get(run_id)
    if run:
        graph_state = compiled_graph.get_state({"configurable": {"thread_id": run_id}})
        pending_approval = bool(graph_state and graph_state.next)

        return RunReportResponse(
            done=run.done,
            error=run.error or None,
            query=run.query,
            current_agent=run.current_agent,
            sql_draft=run.sql_draft or None,
            sql_explanation=run.sql_explanation or None,
            sql_approved=bool(run.approval_data.get("approved")),
            pending_approval=pending_approval,
            insights=run.insights or None,
            content=run.report_content,
            agent_steps=run.agent_steps,
            thinking_segments=run.thinking_segments,
            executions=run.executions,
        )

    async with async_session_maker() as db:
        row = await run_repository.get_run(db, run_id)
        if not row:
            raise HTTPException(status_code=404, detail="Run not found")
        payload = run_repository.run_row_to_report_payload(row)
        return RunReportResponse(**payload)


@router.get("/rl-memory/stats")
async def get_rl_memory_stats():
    memory = get_rl_memory()
    return {
        "trajectory_count": len(memory.trajectories),
        "memory": memory.to_dict(),
    }


@router.get("/rl-memory/trajectories")
async def get_rl_trajectories(limit: int = 20):
    memory = get_rl_memory()
    trajectories = memory.trajectories[-limit:]
    return {
        "trajectories": [
            {
                "query_hash": t.query_hash,
                "intent": t.intent,
                "pipeline": t.pipeline,
                "success": t.success,
                "reward": t.reward,
                "critic_feedback": t.critic_feedback[:200] if t.critic_feedback else "",
                "data_error": t.data_error,
            }
            for t in trajectories
        ]
    }
