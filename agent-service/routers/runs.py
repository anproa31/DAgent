import uuid
import asyncio
import json
from typing import Any, AsyncGenerator, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.types import Command

from agents.graph import compiled_graph
from database import async_session_maker
from models.requests import StartRunRequest, ApproveRequest, RejectRequest
from models.responses import StartRunResponse, ApproveResponse, RejectResponse, RunReportResponse
from repositories import run_repository, session_repository
from run_registry import RUN_STATES
from routers.title import update_session_title_if_empty

router = APIRouter()


class RunState:
    def __init__(self, session_id: str, run_id: str, query: str):
        self.session_id = session_id
        self.run_id = run_id
        self.query = query
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.approval_event: asyncio.Event = asyncio.Event()
        self.approval_data: dict = {}
        self.done: bool = False
        self.report_content: list = []
        self.current_agent: str = ""
        self.sql_draft: str = ""
        self.sql_explanation: str = ""
        self.insights: str = ""
        self.agent_steps: list = []
        self.error: str = ""


def _normalize_report_content(rc: Any) -> List[Any]:
    if rc is None:
        return []
    return rc if isinstance(rc, list) else []


async def _emit_title_updated_if_needed(run: RunState, initial_input: dict) -> None:
    """Persist LLM session title and notify the client before the stream closes."""
    try:
        new_title = await update_session_title_if_empty(
            run.session_id,
            run.query,
            initial_input.get("model") or "",
            initial_input.get("base_url") or "",
            initial_input.get("api_key") or "",
        )
        if new_title:
            await run.event_queue.put(
                {
                    "event": "title_updated",
                    "data": {"session_id": run.session_id, "title": new_title},
                }
            )
    except Exception as te:
        print(f"[runs] title update failed for session {run.session_id}: {te}")


async def _persist_run_to_db(run: RunState) -> None:
    pending_approval = False
    try:
        graph_state = compiled_graph.get_state({"configurable": {"thread_id": run.run_id}})
        pending_approval = bool(graph_state and graph_state.next) and not run.done
    except Exception:
        pending_approval = False

    sql_ok = bool(run.approval_data.get("approved")) if run.approval_data else False

    async with async_session_maker() as db:
        await run_repository.update_run(
            db,
            run.run_id,
            done=run.done,
            error=run.error or None,
            current_agent=run.current_agent or "",
            sql_draft=run.sql_draft or None,
            sql_explanation=run.sql_explanation or None,
            sql_approved=sql_ok,
            pending_approval=pending_approval,
            insights=run.insights or None,
            report_content=_normalize_report_content(run.report_content),
            agent_steps=list(run.agent_steps) if run.agent_steps else [],
        )
        await session_repository.touch_session(db, run.session_id)


async def _run_graph(run: RunState, initial_input: dict):
    """Background task: stream the graph, handle HITL interrupt, and push SSE events."""
    config = {"configurable": {"thread_id": run.run_id}}

    async def _emit(event_type: str, data: dict):
        await run.event_queue.put({"event": event_type, "data": data})

    try:
        await _emit("thinking", {"message": "Starting analysis...", "agent": "orchestrator"})

        # ── First graph run (may pause at interrupt) ──
        async for chunk in compiled_graph.astream(initial_input, config=config, stream_mode="updates"):
            for node_name, node_output in chunk.items():
                if isinstance(node_output, dict):
                    # Update run state for polling endpoint
                    run.current_agent = node_output.get("current_agent", node_name)
                    if node_output.get("agent_steps"):
                        run.agent_steps = node_output["agent_steps"]
                    if node_output.get("sql_draft"):
                        run.sql_draft = node_output["sql_draft"]
                    if node_output.get("sql_explanation"):
                        run.sql_explanation = node_output["sql_explanation"]
                    if node_output.get("insights"):
                        run.insights = node_output["insights"]

                event_data = {
                    "agent": node_name,
                    "current_agent": run.current_agent,
                    "agent_steps": run.agent_steps,
                }
                # Include intent classification when orchestrator reports it
                if node_name == "orchestrator" and isinstance(node_output, dict):
                    intent = node_output.get("intent", "")
                    if intent:
                        event_data["intent"] = intent

                await _emit("agent_update", event_data)

        # ── Check if graph is interrupted (HITL checkpoint) ──
        graph_state = compiled_graph.get_state(config)
        if graph_state.next:
            # Interrupted — collect interrupt value from pending tasks
            interrupt_value = {}
            for task in graph_state.tasks:
                for interrupt_obj in task.interrupts:
                    interrupt_value = interrupt_obj.value
                    break
                if interrupt_value:
                    break

            run.sql_draft = interrupt_value.get("sql", run.sql_draft)
            run.sql_explanation = interrupt_value.get("explanation", "")

            await _emit(
                "sql_generated",
                {
                    "sql": run.sql_draft,
                    "explanation": run.sql_explanation,
                    "query": run.query,
                },
            )

            # Wait for user to approve or reject
            await run.approval_event.wait()
            run.approval_event.clear()

            await _emit(
                "thinking",
                {
                    "message": "Resuming analysis after SQL approval...",
                    "agent": run.current_agent,
                },
            )

            # ── Resume the graph with the approval decision ──
            async for chunk in compiled_graph.astream(
                Command(resume=run.approval_data),
                config=config,
                stream_mode="updates",
            ):
                for node_name, node_output in chunk.items():
                    if isinstance(node_output, dict):
                        run.current_agent = node_output.get("current_agent", node_name)
                        if node_output.get("agent_steps"):
                            run.agent_steps = node_output["agent_steps"]
                        if node_output.get("insights"):
                            run.insights = node_output["insights"]
                        if node_output.get("report_content"):
                            run.report_content = node_output["report_content"]

                    await _emit(
                        "agent_update",
                        {
                            "agent": node_name,
                            "current_agent": run.current_agent,
                            "agent_steps": run.agent_steps,
                        },
                    )

        # ── Collect final state ──
        final_state = compiled_graph.get_state(config)
        if final_state and final_state.values:
            vals = final_state.values
            run.report_content = vals.get("report_content", run.report_content)
            run.insights = vals.get("insights", run.insights)
            run.agent_steps = vals.get("agent_steps", run.agent_steps)
            run.error = vals.get("error", "")

        run.done = True
        await _emit_title_updated_if_needed(run, initial_input)
        await _emit("done", {"content": run.report_content, "insights": run.insights})

    except Exception as e:
        run.error = str(e)
        run.done = True
        await _emit_title_updated_if_needed(run, initial_input)
        await run.event_queue.put({"event": "error", "data": {"message": str(e)}})
        print(f"[runs] graph error for run {run.run_id}: {e}")
    finally:
        try:
            await _persist_run_to_db(run)
        except Exception as pe:
            print(f"[runs] persist error for run {run.run_id}: {pe}")
        RUN_STATES.pop(run.run_id, None)


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/sessions/{session_id}/runs", response_model=StartRunResponse)
async def start_run(session_id: str, body: StartRunRequest):
    """Start a new multi-agent analysis run inside a session."""
    run_id = str(uuid.uuid4())

    async with async_session_maker() as db:
        sess = await session_repository.get_session(db, session_id)
        if not sess:
            raise HTTPException(status_code=404, detail="Session not found")
        await run_repository.create_run(db, run_id, session_id, body.query)
        await session_repository.touch_session(db, session_id)

    run = RunState(session_id=session_id, run_id=run_id, query=body.query)
    RUN_STATES[run_id] = run

    initial_input = {
        "session_id": session_id,
        "run_id": run_id,
        "query": body.query,
        "tables": body.tables,
        "model": body.model,
        "base_url": body.base_url,
        "api_key": body.api_key,
        "schema_info": "",
        "enhanced_context": "",
        "datasources": [],
        "intent": "",
        "execution_mode": "",
        "pipeline": [],
        "current_agent": "",
        "agent_steps": [],
        "sql_draft": "",
        "sql_explanation": "",
        "sql_approved": False,
        "sql_rejection_reason": "",
        "python_code": "",
        "data_summary": "",
        "result_var_names": [],
        "eda_summary": "",
        "insights": "",
        "viz_code": "",
        "viz_var_names": [],
        "report_content": [],
        "done": False,
        "error": "",
    }

    asyncio.create_task(_run_graph(run, initial_input))
    return StartRunResponse(run_id=run_id)


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    """Server-Sent Events stream of agent progress for this run."""
    run = RUN_STATES.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        while True:
            try:
                item = await asyncio.wait_for(run.event_queue.get(), timeout=30.0)
                payload = json.dumps(item["data"])
                yield f"event: {item['event']}\ndata: {payload}\n\n"
                if item["event"] in ("done", "error"):
                    break
            except asyncio.TimeoutError:
                # Heartbeat to keep connection alive
                yield ": heartbeat\n\n"
                if run.done:
                    break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/runs/{run_id}/approve", response_model=ApproveResponse)
async def approve_sql(run_id: str, body: ApproveRequest):
    """Approve the pending SQL (optionally with an edited version)."""
    run = RUN_STATES.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    run.approval_data = {"approved": True, "sql": body.sql or run.sql_draft}
    run.sql_draft = body.sql or run.sql_draft
    run.approval_event.set()
    return ApproveResponse(success=True)


@router.post("/runs/{run_id}/reject", response_model=RejectResponse)
async def reject_sql(run_id: str, body: RejectRequest):
    """Reject the pending SQL and trigger regeneration."""
    run = RUN_STATES.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    run.approval_data = {"approved": False, "reason": body.reason}
    run.approval_event.set()
    return RejectResponse(success=True)


@router.get("/runs/{run_id}/report", response_model=RunReportResponse)
async def get_report(run_id: str):
    """Poll for the current state / final report of a run."""
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
        )

    async with async_session_maker() as db:
        row = await run_repository.get_run(db, run_id)
        if not row:
            raise HTTPException(status_code=404, detail="Run not found")
        payload = run_repository.run_row_to_report_payload(row)
        return RunReportResponse(**payload)
