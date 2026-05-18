import uuid
import asyncio
import json
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.types import Command

from agents.graph import compiled_graph
from models.requests import StartRunRequest, ApproveRequest, RejectRequest
from models.responses import StartRunResponse, ApproveResponse, RejectResponse, RunReportResponse

router = APIRouter()

# Per-run state: event_queue, approval_event, approval_data, final state, done flag
_run_states: dict = {}


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

                await _emit(
                    "agent_update",
                    {
                        "agent": node_name,
                        "current_agent": run.current_agent,
                        "agent_steps": run.agent_steps,
                    },
                )

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
        await _emit("done", {"content": run.report_content, "insights": run.insights})

    except Exception as e:
        run.error = str(e)
        run.done = True
        await run.event_queue.put({"event": "error", "data": {"message": str(e)}})
        print(f"[runs] graph error for run {run.run_id}: {e}")


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/sessions/{session_id}/runs", response_model=StartRunResponse)
async def start_run(session_id: str, body: StartRunRequest):
    """Start a new multi-agent analysis run inside a session."""
    from routers.sessions import sessions

    run_id = str(uuid.uuid4())
    run = RunState(session_id=session_id, run_id=run_id, query=body.query)
    _run_states[run_id] = run

    # Register run in session
    if session_id in sessions:
        sessions[session_id]["runs"].append(run_id)

    initial_input = {
        "session_id": session_id,
        "run_id": run_id,
        "query": body.query,
        "tables": body.tables,
        "model": body.model,
        "base_url": body.base_url,
        "api_key": body.api_key,
        "schema_info": "",
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

    # Launch graph in background
    asyncio.create_task(_run_graph(run, initial_input))
    return StartRunResponse(run_id=run_id)


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: str):
    """Server-Sent Events stream of agent progress for this run."""
    run = _run_states.get(run_id)
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
    run = _run_states.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    run.approval_data = {"approved": True, "sql": body.sql or run.sql_draft}
    run.sql_draft = body.sql or run.sql_draft
    run.approval_event.set()
    return ApproveResponse(success=True)


@router.post("/runs/{run_id}/reject", response_model=RejectResponse)
async def reject_sql(run_id: str, body: RejectRequest):
    """Reject the pending SQL and trigger regeneration."""
    run = _run_states.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    run.approval_data = {"approved": False, "reason": body.reason}
    run.approval_event.set()
    return RejectResponse(success=True)


@router.get("/runs/{run_id}/report", response_model=RunReportResponse)
async def get_report(run_id: str):
    """Poll for the current state / final report of a run."""
    run = _run_states.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

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
