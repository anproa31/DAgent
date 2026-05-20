"""Background LangGraph execution and SSE event streaming."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, List, Optional

from langgraph.types import Command

from agents.planner.analytics_react_agent import MAX_PLANNER_STEPS
from config.settings import HITL_TIMEOUT_SECONDS
from infrastructure.database.connection import async_session_maker
from infrastructure.repositories import run_repository, session_repository
from interfaces.api.session_title import update_session_title_if_empty
from orchestration.state_management.run_registry import RUN_STATES
from orchestration.workflows.graph import compiled_graph


class RunState:
    def __init__(self, session_id: str, run_id: str, query: str):
        self.session_id = session_id
        self.run_id = run_id
        self.query = query
        self.event_queue: asyncio.Queue = asyncio.Queue()
        # Event loop driving this run — captured in run_graph so the planner's
        # streaming token callback (a worker thread) can bridge back to the queue.
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        # Live streaming artifacts (persisted so reload can replay them):
        #  - thinking_segments: {id, agent, step, text} reasoning/generation chunks
        #  - executions: {id, kind, code, log, columns, rows, status, error}
        self.thinking_segments: list = []
        self.executions: list = []
        self.approval_event: asyncio.Event = asyncio.Event()
        self.approval_data: dict = {}
        self.done: bool = False
        self.report_content: list = []
        self.current_agent: str = ""
        self.sql_draft: str = ""
        self.sql_explanation: str = ""
        self.sql_rejection_reason: str = ""
        self.pending_approval_type: str = ""
        self.web_discover_proposal: dict = {}
        self.python_code: str = ""
        self.python_risk: str = ""
        self.insights: str = ""
        self.agent_steps: list = []
        self.error: str = ""
        # Standardized completion/error reporting (solution.md §10).
        self.completion_reason: str = "success"
        self.error_code: str = ""
        self.recoverable: bool = True
        self.affected_step: str = ""
        self.steps_used: int = 0


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _base_event_fields(run: RunState) -> dict:
    """Common fields on every structured SSE event (solution.md §10)."""
    return {
        "run_id": run.run_id,
        "timestamp": _now_iso(),
        "step": run.steps_used,
    }


def make_done_event(run: RunState) -> dict:
    data = _base_event_fields(run)
    data.update(
        {
            "completion_reason": run.completion_reason,
            "steps_used": run.steps_used,
            "steps_budget": MAX_PLANNER_STEPS,
            "content": run.report_content,
            "insights": run.insights,
        }
    )
    return {"event": "done", "data": data}


def make_error_event(
    run: RunState,
    *,
    code: str,
    message: str,
    recoverable: bool,
    affected_step: Optional[str] = None,
) -> dict:
    run.error_code = code
    run.recoverable = recoverable
    if affected_step:
        run.affected_step = affected_step
    data = _base_event_fields(run)
    data.update(
        {
            "code": code,
            "message": message,
            "recoverable": recoverable,
            "affected_step": affected_step or run.affected_step or None,
        }
    )
    return {"event": "error", "data": data}


def _derive_completion_reason(run: RunState) -> str:
    if run.error == "stopped":
        return "user_cancelled"
    if run.steps_used >= MAX_PLANNER_STEPS:
        return "step_limit"
    return "success"


def normalize_report_content(rc: Any) -> List[Any]:
    if rc is None:
        return []
    return rc if isinstance(rc, list) else []


async def emit_title_updated_if_needed(run: RunState, initial_input: dict) -> None:
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


async def persist_run_to_db(run: RunState) -> None:
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
            report_content=normalize_report_content(run.report_content),
            agent_steps=list(run.agent_steps) if run.agent_steps else [],
            thinking_segments=list(run.thinking_segments) if run.thinking_segments else [],
            executions=list(run.executions) if run.executions else [],
        )
        await session_repository.touch_session(db, run.session_id)


async def _emit_execution_result(run: RunState, node_name: str, node_output: dict) -> None:
    """Record + stream a SQL/Python execution card (code + sandbox log)."""
    obs = node_output.get("last_observation") or {}
    artifacts = obs.get("artifacts") or {}

    if node_name == "code_executor":
        kind = "sql"
        code = node_output.get("sql_draft") or artifacts.get("sql_draft") or run.sql_draft or ""
    else:
        kind = "python"
        code = node_output.get("python_code") or artifacts.get("python_code") or run.python_code or ""

    error = node_output.get("error") or obs.get("error") or ""
    execution = {
        "id": f"{kind}-{len(run.executions)}",
        "kind": kind,
        "code": code,
        "log": node_output.get("data_summary") or artifacts.get("data_summary") or "",
        "columns": artifacts.get("columns") or [],
        "rows": int(artifacts.get("rows") or 0),
        "status": "error" if error else "success",
        "error": error,
    }
    run.executions.append(execution)
    await run.event_queue.put(
        {"event": "execution_result", "data": {"run_id": run.run_id, **execution}}
    )


async def _stream_graph_chunks(run: RunState, config: dict, input_or_command):
    async for chunk in compiled_graph.astream(input_or_command, config=config, stream_mode="updates"):
        for node_name, node_output in chunk.items():
            if isinstance(node_output, dict):
                run.current_agent = node_output.get("current_agent", node_name)
                if node_output.get("agent_steps"):
                    run.agent_steps = node_output["agent_steps"]
                if node_output.get("sql_draft"):
                    run.sql_draft = node_output["sql_draft"]
                if node_output.get("sql_explanation"):
                    run.sql_explanation = node_output["sql_explanation"]
                if node_output.get("python_code"):
                    run.python_code = node_output["python_code"]
                if node_output.get("python_risk"):
                    run.python_risk = node_output["python_risk"]
                if node_output.get("insights"):
                    run.insights = node_output["insights"]
                if node_output.get("report_content"):
                    run.report_content = node_output["report_content"]
                if node_output.get("planner_step_index") is not None:
                    run.steps_used = node_output["planner_step_index"]

            event_data = {
                "agent": node_name,
                "current_agent": run.current_agent,
                "agent_steps": run.agent_steps,
            }

            if node_name in ("orchestrator", "planner") and isinstance(node_output, dict):
                intent = node_output.get("intent", "")
                if intent:
                    event_data["intent"] = intent
                execution_mode = node_output.get("execution_mode", "")
                if execution_mode:
                    event_data["execution_mode"] = execution_mode

            if node_name == "planner" and isinstance(node_output, dict):
                planner_history = node_output.get("planner_history", [])
                if planner_history:
                    last_step = planner_history[-1]
                    thought = last_step.get("thought", "")
                    action = last_step.get("action", "")
                    step_index = node_output.get("planner_step_index", len(planner_history))
                    if thought:
                        # Fallback: if token streaming produced no planner segment
                        # this turn (e.g. agent_patterns didn't surface tokens),
                        # seed the segment from the parsed thought so the thinking
                        # view is never empty.
                        if not run.thinking_segments or run.thinking_segments[-1].get("agent") != "planner":
                            run.thinking_segments.append(
                                {
                                    "id": f"planner-{step_index}-{len(run.thinking_segments)}",
                                    "agent": "planner",
                                    "step": step_index,
                                    "text": thought,
                                }
                            )
                        await run.event_queue.put(
                            {
                                "event": "planner_thought",
                                "data": {
                                    "thought": thought,
                                    "action": action,
                                    "step_index": step_index,
                                },
                            }
                        )

            if node_name in ("code_executor", "python") and isinstance(node_output, dict):
                await _emit_execution_result(run, node_name, node_output)

            await run.event_queue.put({"event": "agent_update", "data": event_data})


def _extract_interrupt_value(graph_state) -> dict:
    interrupt_value = {}
    for task in graph_state.tasks:
        for interrupt_obj in task.interrupts:
            interrupt_value = interrupt_obj.value
            break
        if interrupt_value:
            break
    return interrupt_value


async def _handle_hitl_interrupt(run: RunState, config: dict) -> bool:
    """Pause for SQL or web-datasource approval; return True if graph should continue."""
    graph_state = compiled_graph.get_state(config)
    if not graph_state.next:
        return False

    interrupt_value = _extract_interrupt_value(graph_state)
    if not interrupt_value:
        return False

    interrupt_type = interrupt_value.get("type", "sql_review")
    run.pending_approval_type = interrupt_type

    if interrupt_type == "web_datasource_review":
        run.web_discover_proposal = interrupt_value
        await run.event_queue.put(
            {"event": "web_datasource_proposed", "data": interrupt_value}
        )
        resume_message = "Resuming analysis after web datasource approval..."
    elif interrupt_type == "python_review":
        run.python_code = interrupt_value.get("code", "")
        run.python_risk = interrupt_value.get("risk", "medium")
        await run.event_queue.put(
            {
                "event": "python_review_required",
                "data": {
                    "code": run.python_code,
                    "risk": run.python_risk,
                    "query": run.query,
                },
            }
        )
        resume_message = "Resuming analysis after Python approval..."
    else:
        run.sql_draft = interrupt_value.get("sql", run.sql_draft)
        run.sql_explanation = interrupt_value.get("explanation", "")
        await run.event_queue.put(
            {
                "event": "sql_generated",
                "data": {
                    "sql": run.sql_draft,
                    "explanation": run.sql_explanation,
                    "query": run.query,
                },
            }
        )
        resume_message = "Resuming analysis after SQL approval..."

    # HITL TTL (solution.md §6): cancel the run if no decision arrives in time.
    try:
        await asyncio.wait_for(run.approval_event.wait(), timeout=HITL_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        run.done = True
        run.completion_reason = "hitl_timeout"
        run.error = "hitl_timeout"
        minutes = HITL_TIMEOUT_SECONDS // 60
        await run.event_queue.put(
            make_error_event(
                run,
                code="HITL_TIMEOUT",
                message=f"No approval received after {minutes} minutes. Run cancelled.",
                recoverable=False,
                affected_step=interrupt_type,
            )
        )
        return False
    run.approval_event.clear()

    await run.event_queue.put(
        {
            "event": "thinking",
            "data": {"message": resume_message, "agent": run.current_agent},
        }
    )

    await _stream_graph_chunks(run, config, Command(resume=run.approval_data))
    return True


async def run_graph(run: RunState, initial_input: dict) -> None:
    """Background task: stream the graph, handle HITL interrupt, and push SSE events."""
    config = {"configurable": {"thread_id": run.run_id}}
    # Capture the loop here (run_graph executes on the main loop) so worker-thread
    # token callbacks can enqueue events via loop.call_soon_threadsafe.
    run.loop = asyncio.get_running_loop()

    try:
        await run.event_queue.put(
            {"event": "thinking", "data": {"message": "Starting analysis...", "agent": "orchestrator"}}
        )

        await _stream_graph_chunks(run, config, initial_input)

        while await _handle_hitl_interrupt(run, config):
            pass

        # HITL timed out — error event already emitted, nothing more to do.
        if run.completion_reason == "hitl_timeout":
            await emit_title_updated_if_needed(run, initial_input)
            return

        final_state = compiled_graph.get_state(config)
        if final_state and final_state.values:
            vals = final_state.values
            run.report_content = vals.get("report_content", run.report_content)
            run.insights = vals.get("insights", run.insights)
            run.agent_steps = vals.get("agent_steps", run.agent_steps)
            run.steps_used = vals.get("planner_step_index", run.steps_used)
            # Preserve a "stopped"/timeout reason already set; otherwise mirror state error.
            if not run.error:
                run.error = vals.get("error", "")

        run.done = True
        run.completion_reason = _derive_completion_reason(run)
        await emit_title_updated_if_needed(run, initial_input)
        await run.event_queue.put(make_done_event(run))

    except Exception as e:
        run.error = str(e)
        run.done = True
        run.completion_reason = "error"
        await emit_title_updated_if_needed(run, initial_input)
        await run.event_queue.put(
            make_error_event(
                run,
                code="GRAPH_ERROR",
                message=str(e),
                recoverable=False,
                affected_step=run.current_agent,
            )
        )
        print(f"[runs] graph error for run {run.run_id}: {e}")
    finally:
        try:
            await persist_run_to_db(run)
        except Exception as pe:
            print(f"[runs] persist error for run {run.run_id}: {pe}")
        RUN_STATES.pop(run.run_id, None)


def build_initial_state(
    session_id: str,
    run_id: str,
    query: str,
    tables: list,
    model: str,
    base_url: str,
    api_key: str,
) -> dict:
    """Construct the LangGraph initial state dict for a new run."""
    return {
        "session_id": session_id,
        "run_id": run_id,
        "query": query,
        "tables": tables,
        "model": model,
        "base_url": base_url,
        "api_key": api_key,
        "schema_info": "",
        "enhanced_context": "",
        "datasources": [],
        "intent": "",
        "execution_mode": "",
        "orchestration_mode": "FIXED",
        "pipeline": [],
        "execution_plan": [],
        "current_agent": "",
        "agent_steps": [],
        "planner_history": [],
        "last_observation": {},
        "current_action": "",
        "planner_step_index": 0,
        "completed_actions": [],
        "reflection_cycle": 0,
        "max_reflection_cycles": 1,
        "reflection": "",
        "refined_output": "",
        "needs_refinement": False,
        "continue_reflection": False,
        "reflection_needs_rerun": False,
        "rerun_count": 0,
        "python_risk": "",
        "completion_reason": "",
        "sql_draft": "",
        "sql_explanation": "",
        "sql_approved": False,
        "sql_rejection_reason": "",
        "web_discover_proposal": {},
        "web_discover_approved": False,
        "web_discover_rejection_reason": "",
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


async def sse_event_generator(run: RunState) -> AsyncGenerator[str, None]:
    while True:
        try:
            item = await asyncio.wait_for(run.event_queue.get(), timeout=30.0)
            payload = json.dumps(item["data"])
            yield f"event: {item['event']}\ndata: {payload}\n\n"
            if item["event"] in ("done", "error"):
                break
        except asyncio.TimeoutError:
            yield ": heartbeat\n\n"
            if run.done:
                break
