"""Background LangGraph execution and SSE event streaming."""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator, List

from langgraph.types import Command

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
        self.insights: str = ""
        self.agent_steps: list = []
        self.error: str = ""


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
        )
        await session_repository.touch_session(db, run.session_id)


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
                if node_output.get("insights"):
                    run.insights = node_output["insights"]
                if node_output.get("report_content"):
                    run.report_content = node_output["report_content"]

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

    await run.approval_event.wait()
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

    try:
        await run.event_queue.put(
            {"event": "thinking", "data": {"message": "Starting analysis...", "agent": "orchestrator"}}
        )

        await _stream_graph_chunks(run, config, initial_input)

        while await _handle_hitl_interrupt(run, config):
            pass

        final_state = compiled_graph.get_state(config)
        if final_state and final_state.values:
            vals = final_state.values
            run.report_content = vals.get("report_content", run.report_content)
            run.insights = vals.get("insights", run.insights)
            run.agent_steps = vals.get("agent_steps", run.agent_steps)
            run.error = vals.get("error", "")

        run.done = True
        await emit_title_updated_if_needed(run, initial_input)
        await run.event_queue.put({"event": "done", "data": {"content": run.report_content, "insights": run.insights}})

    except Exception as e:
        run.error = str(e)
        run.done = True
        await emit_title_updated_if_needed(run, initial_input)
        await run.event_queue.put({"event": "error", "data": {"message": str(e)}})
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
        "replan_count": 0,
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
