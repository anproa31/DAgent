"""Real-time token streaming of agent reasoning/generation.

Emits ``thinking_chunk`` SSE events as the model produces tokens, so the
frontend can render the model's thinking live. Two entry points:

* ``make_delta_emitter`` — async callback for agents that call
  :func:`utils.llm_client.chat_complete` on the main event loop.
* ``ThinkingTokenCallback`` — LangChain callback for the ReAct planner, which
  runs inside ``asyncio.to_thread`` (a worker thread). It reads the active run
  from a contextvar (propagated into the thread by ``asyncio.to_thread``) and
  bridges back to the run's asyncio queue via the captured loop.

Token deltas are also accumulated into ``run.thinking_segments`` (grouped by
agent + planner step) so they can be persisted and replayed after reload.
"""

from __future__ import annotations

import contextvars
from typing import Any, Awaitable, Callable, Optional, Tuple

from langchain_core.callbacks.base import BaseCallbackHandler

from orchestration.state_management.run_registry import RUN_STATES

# Active (run_id, agent_label) for thread-bound code paths (the planner). Set by
# the planner node around its ``asyncio.to_thread`` call; ``None`` everywhere
# else. ``asyncio.to_thread`` copies the current context into the worker thread,
# so the value set before the call is visible inside the callback.
current_run_var: contextvars.ContextVar[Optional[Tuple[str, str]]] = contextvars.ContextVar(
    "current_run_var", default=None
)


def accumulate_segment(run: Any, agent: str, delta: str) -> None:
    """Append a token delta to the open thinking segment for (agent, step).

    A new segment is started whenever the agent or planner step changes, so the
    UI can show one collapsible block per reasoning/generation phase.
    """
    if not delta:
        return
    step = getattr(run, "steps_used", 0)
    segments = run.thinking_segments
    if segments and segments[-1].get("agent") == agent and segments[-1].get("step") == step:
        segments[-1]["text"] += delta
    else:
        segments.append(
            {
                "id": f"{agent}-{step}-{len(segments)}",
                "agent": agent,
                "step": step,
                "text": delta,
            }
        )


def _thinking_chunk_event(run_id: str, agent: str, step: int, delta: str) -> dict:
    return {
        "event": "thinking_chunk",
        "data": {"run_id": run_id, "agent": agent, "step": step, "delta": delta},
    }


def make_delta_emitter(run_id: str, agent: str) -> Callable[[str], Awaitable[None]]:
    """Build an async ``on_delta(text)`` emitter for a chat_complete call."""

    async def emit(delta: str) -> None:
        run = RUN_STATES.get(run_id)
        if not run or not delta:
            return
        accumulate_segment(run, agent, delta)
        await run.event_queue.put(
            _thinking_chunk_event(run_id, agent, getattr(run, "steps_used", 0), delta)
        )

    return emit


class ThinkingTokenCallback(BaseCallbackHandler):
    """LangChain callback that streams planner tokens to the run's SSE queue.

    Stateless — it resolves the active run from ``current_run_var`` on every
    token, so a single shared/cached planner LLM stays correct under concurrent
    runs (each planner call runs in its own thread with its own copied context).
    """

    def on_llm_new_token(self, token: str, **kwargs: Any) -> None:  # noqa: D401
        ctx = current_run_var.get()
        if not ctx or not token:
            return
        run_id, agent = ctx
        run = RUN_STATES.get(run_id)
        if not run:
            return
        step = getattr(run, "steps_used", 0)
        accumulate_segment(run, agent, token)
        event = _thinking_chunk_event(run_id, agent, step, token)
        loop = getattr(run, "loop", None)
        if loop is not None:
            loop.call_soon_threadsafe(run.event_queue.put_nowait, event)
        else:  # pragma: no cover — same-loop fallback
            try:
                run.event_queue.put_nowait(event)
            except Exception:
                pass
