import uuid
import asyncio
import json
from typing import Any, AsyncGenerator, List

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from langgraph.types import Command

from agents.graph import compiled_graph
from agents.reflection_rl import get_rl_memory
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
        self.sql_rejection_reason: str = ""
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
                # Include intent classification when orchestrator/planner reports it
                if node_name in ("orchestrator", "planner") and isinstance(node_output, dict):
                    intent = node_output.get("intent", "")
                    if intent:
                        event_data["intent"] = intent
                    execution_mode = node_output.get("execution_mode", "")
                    if execution_mode:
                        event_data["execution_mode"] = execution_mode

                # Emit planner thought events for ReAct transparency
                if node_name == "planner" and isinstance(node_output, dict):
                    planner_history = node_output.get("planner_history", [])
                    if planner_history:
                        last_step = planner_history[-1]
                        thought = last_step.get("thought", "")
                        action = last_step.get("action", "")
                        step_index = node_output.get("planner_step_index", len(planner_history))
                        if thought:
                            await _emit("planner_thought", {
                                "thought": thought,
                                "action": action,
                                "step_index": step_index,
                            })

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

            # ── Check for another interrupt (re-plan may have triggered new SQL) ──
            # Loop to handle multiple HITL pauses (e.g., reflection re-plan → new SQL)
            while True:
                graph_state = compiled_graph.get_state(config)
                if not graph_state.next:
                    break  # Graph completed

                # Check if there's a new interrupt
                interrupt_value = {}
                for task in graph_state.tasks:
                    for interrupt_obj in task.interrupts:
                        interrupt_value = interrupt_obj.value
                        break
                    if interrupt_value:
                        break

                if not interrupt_value:
                    break  # No interrupt, graph is stuck or done

                # New SQL generated during re-plan — pause for approval again
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

                # Resume graph with new approval
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
        # ReAct planner fields
        "planner_history": [],
        "last_observation": {},
        "current_action": "",
        "planner_step_index": 0,
        "completed_actions": [],
        "replan_count": 0,
        # Legacy fields
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

    # Store edited SQL if provided, otherwise keep current draft
    edited_sql = body.sql if body.sql else run.sql_draft
    run.approval_data = {"approved": False, "reason": body.reason, "sql": edited_sql}
    run.sql_draft = edited_sql
    run.sql_rejection_reason = body.reason
    run.approval_event.set()
    return RejectResponse(success=True)


@router.post("/runs/{run_id}/stop")
async def stop_run(run_id: str):
    """Stop/cancel a run. Closes the SSE stream and marks the run as stopped."""
    run = RUN_STATES.get(run_id)
    if not run:
        # Run not in memory — may already be completed or never existed
        # Still return success so client can clean up local state
        return {"success": True, "already_stopped": True}

    # Mark as done to stop the graph loop
    run.done = True
    run.error = "stopped"
    # Drain any pending approval
    if run.approval_event.is_set():
        run.approval_event.clear()
    run.approval_data = {"approved": False, "reason": "User stopped the run"}
    run.approval_event.set()

    # Persist stopped state
    try:
        await _persist_run_to_db(run)
    except Exception as pe:
        print(f"[runs] stop persist error for run {run_id}: {pe}")

    return {"success": True, "already_stopped": False}


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


@router.get("/rl-memory/stats")
async def get_rl_memory_stats():
    """Get RL reflection memory statistics for debugging/monitoring."""
    memory = get_rl_memory()
    return {
        "trajectory_count": len(memory.trajectories),
        "memory": memory.to_dict(),
    }


@router.get("/rl-memory/trajectories")
async def get_rl_trajectories(limit: int = 20):
    """Get recent RL trajectories for debugging."""
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
