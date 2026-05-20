"""Error boundary for worker nodes (solution.md §9).

Every worker runs inside a boundary that converts crashes and timeouts into a
structured error ``Observation`` instead of killing the run. The planner then
sees ``status="error"`` and decides what to do next, rather than the whole
LangGraph execution aborting.

HITL nodes raise ``GraphInterrupt`` via ``interrupt()`` — that control-flow
signal must propagate untouched, so it is never wrapped as an error.
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Optional

from langgraph.errors import GraphInterrupt

from agents.shared.observations import create_observation
from agents.shared.state import AgentState
from config.settings import WORKER_MAX_RETRIES, WORKER_TIMEOUT_SECONDS
from utils.agent_logger import get_logger

logger = get_logger("error_boundary")

WorkerFn = Callable[[AgentState], Awaitable[dict]]


def with_error_boundary(
    worker_fn: WorkerFn,
    agent_name: str,
    *,
    timeout: Optional[float] = WORKER_TIMEOUT_SECONDS,
    max_retries: int = WORKER_MAX_RETRIES,
) -> WorkerFn:
    """Wrap a worker node so failures become error observations.

    ``timeout=None`` disables the wall-clock guard (use for HITL nodes whose
    pause time is bounded separately by the approval TTL).
    """

    async def _wrapped(state: AgentState) -> dict:
        last_error: Optional[BaseException] = None
        for attempt in range(max_retries + 1):
            try:
                if timeout is not None:
                    return await asyncio.wait_for(worker_fn(state), timeout=timeout)
                return await worker_fn(state)
            except GraphInterrupt:
                raise  # HITL pause — must reach the orchestrator, not be swallowed.
            except asyncio.TimeoutError as exc:
                last_error = exc
                logger.warning("%s timed out (attempt %d)", agent_name, attempt + 1)
                if attempt < max_retries:
                    continue
                return _error_patch(
                    state,
                    agent_name,
                    summary=f"{agent_name} timeout",
                    error=f"Exceeded {timeout}s",
                    next_hint="Try a simpler request or a different action.",
                )
            except Exception as exc:  # noqa: BLE001 — boundary converts to observation
                last_error = exc
                logger.exception("%s crashed (attempt %d)", agent_name, attempt + 1)
                if attempt < max_retries:
                    continue
                return _error_patch(
                    state,
                    agent_name,
                    summary=f"{agent_name} crashed: {type(exc).__name__}",
                    error=str(exc),
                    next_hint="Skip this step and continue with the data already gathered.",
                )
        # Defensive: loop always returns above.
        return _error_patch(
            state,
            agent_name,
            summary=f"{agent_name} failed",
            error=str(last_error) if last_error else "unknown error",
            next_hint="Skip this step and continue.",
        )

    _wrapped.__name__ = getattr(worker_fn, "__name__", agent_name)
    return _wrapped


def _error_patch(
    state: AgentState,
    agent_name: str,
    *,
    summary: str,
    error: str,
    next_hint: str,
) -> dict:
    obs = create_observation(
        agent_name=agent_name,
        status="error",
        summary=summary,
        artifacts={},
        error=error,
        next_hint=next_hint,
    )
    return {
        "current_agent": agent_name,
        "error": f"{agent_name} error: {error}",
        "agent_steps": state.get("agent_steps", []) + [agent_name],
        "last_observation": obs,
    }
