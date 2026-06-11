"""Execution-mode decider — the user's "exec" agent.

Replaces the orchestrator's upfront SQL-vs-Python guess with a runtime decision.
The planner emits a generic ``exec`` action; this node inspects the task and picks
the most efficient tool (SQL or Python), sets ``execution_mode``, then the graph
routes to the existing ``sql`` or ``python`` worker. This fixes cases like a t-test
that SQL cannot express well being forced down the SQL path.
"""

from __future__ import annotations

import json
import re

from agents.shared.state import AgentState
from utils.agent_logger import get_logger
from utils.llm_client import chat_complete, get_async_client
from utils.prompts import EXEC_DECISION_PROMPT, format_semantic_context_for_prompt

logger = get_logger("exec_router")

# Heuristic fallback when the LLM decision call fails — these tasks need Python.
_PYTHON_SIGNALS = re.compile(
    r"\b(t[\s-]?test|chi[\s-]?square|anova|regression|correlat\w*|hypothesis|"
    r"p[\s-]?value|confidence\s+interval|z[\s-]?score|distribution|outlier\w*|"
    r"cluster\w*|forecast\w*|predict\w*|machine\s+learning|pivot|melt|"
    r"scipy|statsmodels|sklearn|standard\s+deviation|variance|percentile|quantile)\b",
    re.I,
)


async def exec_decider_node(state: AgentState) -> dict:
    """Choose sql vs python for the current data/analysis step."""
    query = state.get("query", "")
    logger.info("enter query=%r", query[:80])

    # Already have data from a prior exec step — no re-decision, just pass through.
    # (The sql/python workers also short-circuit, but this avoids the round-trip.)
    if state.get("result_var_names"):
        mode = state.get("execution_mode") or "sql"
        logger.info("data already available — passthrough execution_mode=%s", mode)
        return {"current_agent": "exec", "execution_mode": mode}

    # Fast path: pure retrieval is virtually always SQL — skip the LLM decision.
    if state.get("intent") == "RETRIEVAL":
        logger.info("RETRIEVAL intent — defaulting exec to sql")
        return {
            "current_agent": "exec",
            "execution_mode": "sql",
            "agent_steps": state.get("agent_steps", []) + ["exec"],
        }

    client = get_async_client(state.get("base_url", ""), state.get("api_key", ""))
    model = state.get("model", "")
    schema = state.get("schema_info", "No schema available")
    ctx = format_semantic_context_for_prompt(state.get("enhanced_context", ""))

    mode = "sql"
    try:
        raw = await chat_complete(
            client,
            model,
            [
                {"role": "system", "content": EXEC_DECISION_PROMPT.format(context=ctx, schema=schema)},
                {"role": "user", "content": query},
            ],
            temperature=0.0,
            log_tag="exec_decider",
        )
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            decision = json.loads(match.group())
            chosen = str(decision.get("execution_mode", "")).lower().strip()
            if chosen in ("sql", "python"):
                mode = chosen
                logger.info("exec decision: %s (%s)", mode, str(decision.get("reason", ""))[:80])
    except Exception as exc:
        mode = "python" if _PYTHON_SIGNALS.search(query) else "sql"
        logger.warning("exec LLM decision failed, heuristic → %s: %s", mode, exc)

    logger.info("exit execution_mode=%s", mode)
    return {
        "current_agent": "exec",
        "execution_mode": mode,
        "agent_steps": state.get("agent_steps", []) + ["exec"],
    }


def route_after_exec(state: AgentState) -> str:
    """Route to the worker matching the chosen execution_mode."""
    mode = state.get("execution_mode", "sql")
    target = "python" if mode == "python" else "sql"
    logger.info("route execution_mode=%s -> %s", mode, target)
    return target
