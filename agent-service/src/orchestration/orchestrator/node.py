"""Initial query analysis: schema context, intent, and pipeline selection."""

from __future__ import annotations

import json
import re
from typing import List

from agents.reflection.memory import get_policy_suggestion
from agents.shared.state import AgentState
from context.context_engine import get_enhanced_context
from context.schema_service import (
    combined_markdown_from_payload,
    fetch_schema_payload,
    get_datasources,
)
from orchestration.routing.intent_classifier import (
    _VIZ_ONLY_PATTERNS,
    _LIGHT_ANALYTICAL_PATTERNS,
    quick_classify,
)
from orchestration.routing.pipeline import normalise_pipeline
from orchestration.routing.plan import (
    build_execution_plan,
    detect_explore_intent,
    select_orchestration_mode,
)
from utils.agent_logger import get_logger
from utils.llm_client import chat_complete, get_async_client
from utils.prompts import ORCHESTRATOR_SYSTEM, PLAN_VALIDATION_PROMPT

logger = get_logger("orchestrator")


def _has_viz_request(query: str) -> bool:
    return any(p.search(query) for p in _VIZ_ONLY_PATTERNS)


def _has_light_analytical(query: str) -> bool:
    return any(p.search(query) for p in _LIGHT_ANALYTICAL_PATTERNS)


def _enforce_analytical_pipeline(quick_intent: str, query: str, llm_pipeline: List[str]) -> List[str]:
    """Guarantee the analysis steps implied by the detected analytical level.

    The LLM router often returns a thin pipeline for analytical queries (e.g.
    "analyze the correlation between A and B" → just compute the number, no
    interpretation). This re-derives the worker steps from ``quick_intent`` so an
    ``insight`` step is always present for analytical work, while honoring any
    extra analysis step the LLM added and the user's explicit viz request.

    Returns a sql-term pipeline; ``normalise_pipeline`` collapses the data step
    to ``exec`` afterwards.
    """
    llm_extras = [s for s in llm_pipeline if s in ("eda", "insight", "viz")]
    want_viz = _has_viz_request(query) or "viz" in llm_extras

    steps: List[str] = []
    if quick_intent == "ANALYTICAL":
        steps = ["eda", "insight"]
    elif quick_intent == "LIGHT_ANALYTICAL":
        steps = ["insight"]
    # VIZ_ONLY has no analysis baseline (pure chart)

    if want_viz or quick_intent == "VIZ_ONLY":
        steps.append("viz")

    # Honor any extra analysis step the LLM chose (e.g. eda on a LIGHT query).
    for step in llm_extras:
        if step not in steps:
            steps.append(step)

    order = {"eda": 0, "insight": 1, "viz": 2}
    ordered = sorted(set(steps), key=lambda s: order.get(s, 9))
    return ["sql"] + ordered


async def _validate_pipeline_with_react(
    client,
    model: str,
    query: str,
    pipeline: List[str],
    intent: str,
) -> List[str]:
    """One ReAct reasoning step to validate/correct the pipeline (DB-GPT PlannerAgent pattern).

    Runs a fast zero-temperature LLM call to check whether each proposed step is
    actually needed. Falls back to the original pipeline on any parse error so the
    orchestrator never blocks.
    """
    prompt = PLAN_VALIDATION_PROMPT.format(
        query=query,
        intent=intent,
        proposed_pipeline=json.dumps(pipeline),
    )
    try:
        raw = await chat_complete(
            client,
            model,
            [
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Validate pipeline for: {query}"},
            ],
            temperature=0.0,
            log_tag="plan_validator",
        )
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            result = json.loads(match.group())
            decision = result.get("decision", "accept")
            validated = result.get("pipeline", pipeline)
            thought = result.get("thought", "")
            if decision == "revise" and isinstance(validated, list) and validated:
                logger.info(
                    "plan_validator revised pipeline %s → %s | thought: %s",
                    pipeline,
                    validated,
                    thought[:120],
                )
                return validated
    except Exception as exc:
        logger.warning("plan_validator error — keeping original pipeline: %s", exc)
    return pipeline


async def orchestrator_node(state: AgentState) -> dict:
    """Analyse the query, fetch schema + datasources, and choose the pipeline."""
    logger.info("enter query=%r", state["query"][:80])

    tables_arg = state.get("tables")
    schema_payload = await fetch_schema_payload(tables_arg)

    schema_info = (state.get("schema_info") or "").strip()
    if not schema_info:
        if schema_payload:
            schema_info = combined_markdown_from_payload(schema_payload, tables_arg)
        else:
            schema_info = "Schema unavailable"

    datasources = state.get("datasources") or await get_datasources()

    raw_context = ""
    if schema_payload:
        ctx = schema_payload.get("context")
        if isinstance(ctx, str):
            raw_context = ctx

    fallback_enhanced = raw_context.strip() or schema_info
    enhanced_context = await get_enhanced_context(
        raw_context,
        state.get("query", ""),
        datasources=datasources or None,
        fallback=fallback_enhanced,
    )

    quick_intent = quick_classify(state.get("query", ""))
    intent = "RETRIEVAL"
    pipeline = ["sql"]
    execution_mode = "sql"
    query = state.get("query", "")

    if detect_explore_intent(query) and quick_intent not in ("ANALYTICAL",):
        logger.info("explore intent detected — upgrading to ANALYTICAL pipeline")
        quick_intent = "ANALYTICAL"

    rl_suggestion = get_policy_suggestion(state.get("query", ""), quick_intent or "RETRIEVAL")
    if rl_suggestion and rl_suggestion.get("confidence", 0) > 0.7:
        suggested_pipeline = rl_suggestion.get("pipeline", [])
        logger.info("RL suggestion (high confidence): %s", suggested_pipeline)
        pipeline = suggested_pipeline
        execution_mode = "python" if "python" in pipeline else "sql"
        intent = quick_intent or rl_suggestion.get("intent", intent)

    client = get_async_client(state.get("base_url", ""), state.get("api_key", ""))
    model = state.get("model", "")

    if quick_intent == "RETRIEVAL":
        logger.info("quick-classified as RETRIEVAL, skipping LLM router")
    else:
        datasources_summary = "\n".join(
            f"- {ds.get('name')} ({ds.get('kind')}/{ds.get('type')}) "
            f"with views: {', '.join(ds.get('view_names', []))}"
            for ds in datasources
        ) or "(no datasources registered)"

        messages = [
            {"role": "system", "content": ORCHESTRATOR_SYSTEM},
            {
                "role": "user",
                "content": (
                    f"Registered datasources:\n{datasources_summary}\n\n"
                    f"Datasource schema:\n{schema_info}\n\n"
                    f"User query: {state['query']}"
                ),
            },
        ]

        try:
            raw = await chat_complete(client, model, messages, temperature=0.1, log_tag="orchestrator")
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                decision = json.loads(match.group())
                intent = decision.get("intent", intent).upper()
                execution_mode = decision.get("execution_mode", execution_mode).lower()
                pipeline = decision.get("pipeline", pipeline)
        except Exception as exc:
            logger.warning("LLM error, using defaults: %s", exc)

    # ReAct plan validation: prune steps the LLM over-added (runs before
    # enforcement so it can only trim non-essential steps, never the analytical
    # minimum). Skip when there are no analysis steps to prune.
    if quick_intent != "RETRIEVAL" and any(s in pipeline for s in ("eda", "insight", "viz")):
        pipeline = await _validate_pipeline_with_react(client, model, query, pipeline, intent)

    # Enforce the analytical depth implied by classification — FINAL authority.
    # Guarantees an interpretation step (insight) for any analytical query, even
    # when the LLM/validator returned only a compute step (e.g. "analyze the
    # correlation between A and B" → just the number). Spectrum: intent_classifier.py.
    effective_level = quick_intent
    if effective_level not in ("ANALYTICAL", "LIGHT_ANALYTICAL", "VIZ_ONLY") and intent == "ANALYTICAL":
        # quick_classify missed it but the LLM router flagged analytical —
        # ensure at least an insight step so the result is interpreted.
        effective_level = "LIGHT_ANALYTICAL"

    if effective_level in ("ANALYTICAL", "LIGHT_ANALYTICAL", "VIZ_ONLY"):
        intent = "ANALYTICAL"
        pipeline = _enforce_analytical_pipeline(effective_level, query, pipeline)
        logger.info("enforced %s pipeline → %s", effective_level, pipeline)

    if execution_mode not in ("sql", "python"):
        execution_mode = "sql"

    orchestration_mode = select_orchestration_mode(intent, query)
    pipeline = normalise_pipeline(
        pipeline,
        execution_mode,
        intent,
        orchestration_mode=orchestration_mode,
        query=query,
    )

    execution_plan = build_execution_plan(pipeline, intent, execution_mode)

    logger.info(
        "exit intent=%s mode=%s orchestration=%s pipeline=%s plan_steps=%d",
        intent,
        execution_mode,
        orchestration_mode,
        pipeline,
        len(execution_plan),
    )

    return {
        "schema_info": schema_info,
        "enhanced_context": enhanced_context,
        "datasources": datasources,
        "intent": intent,
        "execution_mode": execution_mode,
        "orchestration_mode": orchestration_mode,
        "pipeline": pipeline,
        "execution_plan": execution_plan,
        "current_agent": "orchestrator",
        "agent_steps": state.get("agent_steps", []) + ["orchestrator"],
    }
