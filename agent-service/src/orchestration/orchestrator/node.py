"""Initial query analysis: schema context, intent, and pipeline selection."""

from __future__ import annotations

import json
import re

from agents.reflection.memory import get_policy_suggestion
from agents.shared.state import AgentState
from context.context_engine import get_enhanced_context
from context.schema_service import (
    combined_markdown_from_payload,
    fetch_schema_payload,
    get_datasources,
)
from orchestration.routing.intent_classifier import quick_classify
from orchestration.routing.pipeline import normalise_pipeline
from orchestration.routing.plan import (
    build_execution_plan,
    detect_explore_intent,
    select_orchestration_mode,
    update_plan_from_reflection,
)
from utils.agent_logger import get_logger
from utils.llm_client import chat_complete, get_async_client
from utils.prompts import ORCHESTRATOR_SYSTEM

logger = get_logger("orchestrator")


async def orchestrator_node(state: AgentState) -> dict:
    """Analyse the query, fetch schema + datasources, and choose the pipeline."""
    replan_count = state.get("replan_count", 0)
    reflection_feedback = state.get("reflection_feedback", "")
    reflection_replan_reason = state.get("reflection_replan_reason", "")
    is_replan = bool(reflection_feedback or reflection_replan_reason)

    logger.info(
        "enter query=%r replan=%s count=%d",
        state["query"][:80],
        is_replan,
        replan_count,
    )

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

    if detect_explore_intent(query) and quick_intent != "ANALYTICAL":
        logger.info("explore intent detected — upgrading to ANALYTICAL pipeline")
        quick_intent = "ANALYTICAL"

    rl_suggestion = get_policy_suggestion(state.get("query", ""), quick_intent or "RETRIEVAL")
    if rl_suggestion and rl_suggestion.get("confidence", 0) > 0.7:
        suggested_pipeline = rl_suggestion.get("pipeline", [])
        logger.info("RL suggestion (high confidence): %s", suggested_pipeline)
        pipeline = suggested_pipeline
        execution_mode = "python" if "python" in pipeline else "sql"
        intent = quick_intent or rl_suggestion.get("intent", intent)

    if quick_intent == "RETRIEVAL":
        logger.info("quick-classified as RETRIEVAL, skipping LLM router")
    else:
        client = get_async_client(state.get("base_url", ""), state.get("api_key", ""))
        model = state.get("model", "")

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

        if quick_intent == "ANALYTICAL" and intent != "ANALYTICAL":
            logger.info("heuristic forced ANALYTICAL (matched analytical keywords)")
            intent = "ANALYTICAL"
            if pipeline == ["sql"]:
                pipeline = ["sql", "eda", "insight", "viz"]

    if execution_mode not in ("sql", "python"):
        execution_mode = "sql"

    orchestration_mode = select_orchestration_mode(
        intent,
        query,
        is_replan=is_replan,
    )
    pipeline = normalise_pipeline(
        pipeline,
        execution_mode,
        intent,
        orchestration_mode=orchestration_mode,
        query=query,
    )

    execution_plan = build_execution_plan(pipeline, intent, execution_mode)

    if is_replan:
        execution_plan = update_plan_from_reflection(
            execution_plan,
            reflection_feedback,
            execution_mode,
        )
        pipeline = [
            step["action"]
            for step in execution_plan
            if step.get("action") not in ("generate_result", "finish")
        ]
        pipeline = normalise_pipeline(
            pipeline,
            execution_mode,
            intent,
            orchestration_mode="EXPLORE",
            query=query,
        )
        replan_count += 1
        logger.info("adjusted plan for reflection: %s", pipeline)

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
        "replan_count": replan_count,
        "current_agent": "orchestrator",
        "agent_steps": state.get("agent_steps", []) + ["orchestrator"],
    }
