import json
import re

from agents.state import AgentState
from services.context_engine import get_enhanced_context
from services.schema_service import (
    combined_markdown_from_payload,
    fetch_schema_payload,
    get_datasources,
)
from utils.agent_logger import get_logger
from utils.llm_client import chat_complete, get_async_client
from utils.prompts import ORCHESTRATOR_SYSTEM
from agents.reflection_rl import get_policy_suggestion

logger = get_logger("orchestrator")


# Regex patterns that strongly indicate a pure retrieval query. These take
# precedence over the LLM classifier because borderline phrasings like
# "show me 5 employees information" tend to flip the LLM to ANALYTICAL even
# though the user clearly just wants the rows.
_RETRIEVAL_PATTERNS = [
    re.compile(r"^\s*(show|list|display|print|return|give\s+me|fetch|get|find)\b", re.I),
    re.compile(r"\b(first|last|top|bottom)\s+\d+\b", re.I),
    re.compile(r"\b\d+\s+(rows?|records?|entries|employees?|customers?|orders?|items?|users?|rows|records)\b", re.I),
    re.compile(r"^\s*(how many|count\s+of|number\s+of|total\s+number)\b", re.I),
    re.compile(r"^\s*(what\s+(?:is|are)\s+the)\s+", re.I),
]

# Strong analytical signals — if any match we must not short-circuit to RETRIEVAL.
_ANALYTICAL_PATTERNS = [
    re.compile(r"\b(why|how come|reason|cause|driver|correlat|trend|forecast|predict|insight|analy[sz]e|analysis|pattern|distribution|outlier|cluster|segment|t[\s-]?test|chi[\s-]?square|anova|regression|hypothesis|p[\s-]?value|significance)\b", re.I),
    re.compile(r"\b(compare|breakdown|over\s+time|by\s+\w+\s+over)\b", re.I),
    re.compile(r"\b(plot|chart|visuali[sz]e|graph|histogram|scatter|heatmap|bar\s+chart)\b", re.I),
    re.compile(r"\b(summary|summari[sz]e|report)\b", re.I),
]


def _quick_classify(query: str) -> str:
    """Deterministic retrieval-vs-analytical heuristic.

    Returns ``"RETRIEVAL"``, ``"ANALYTICAL"`` or ``""`` (unknown).
    Used as a guard rail so the LLM cannot drift on obviously simple
    look-up queries.
    """
    if not query or len(query.strip()) < 3:
        return ""
    if any(p.search(query) for p in _ANALYTICAL_PATTERNS):
        return "ANALYTICAL"
    if any(p.search(query) for p in _RETRIEVAL_PATTERNS):
        return "RETRIEVAL"
    return ""


async def orchestrator_node(state: AgentState) -> dict:
    """Analyse the query, fetch schema + datasources, and choose the pipeline.

    On re-plan from reflection: uses feedback to adjust pipeline.
    Tracks replan_count to avoid infinite loops.
    """
    replan_count = state.get("replan_count", 0)
    reflection_feedback = state.get("reflection_feedback", "")
    is_replan = replan_count > 0 and bool(reflection_feedback)

    logger.info(
        "enter query=%r replan=%s count=%d",
        state["query"][:80],
        is_replan,
        replan_count,
    )

    # Schema (markdown) + aggregated semantic context + structured datasource list.
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

    quick_intent = _quick_classify(state.get("query", ""))
    intent = "RETRIEVAL"  # safer default than ANALYTICAL — fewer side-quests
    pipeline = ["sql"]
    execution_mode = "sql"

    # Check RL memory for historically successful pipelines (before LLM classification)
    rl_suggestion = get_policy_suggestion(state.get("query", ""), quick_intent or "RETRIEVAL")
    if rl_suggestion and rl_suggestion.get("confidence", 0) > 0.7:
        # High-confidence suggestion from RL memory — use it directly
        suggested_pipeline = rl_suggestion.get("pipeline", [])
        logger.info("RL suggestion (high confidence): %s", suggested_pipeline)
        pipeline = suggested_pipeline
        execution_mode = "python" if "python" in pipeline else "sql"
        intent = quick_intent or rl_suggestion.get("intent", intent)

    if quick_intent == "RETRIEVAL":
        # Deterministic short-circuit: obvious lookup queries skip the LLM
        # classifier entirely so the agent doesn't tack on EDA/insight/viz.
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

        # Strong analytical signals override an LLM "RETRIEVAL" classification
        # (e.g. when the user asks "why are employees leaving?" with a count
        # context, the LLM sometimes returns RETRIEVAL).
        if quick_intent == "ANALYTICAL" and intent != "ANALYTICAL":
            logger.info("heuristic forced ANALYTICAL (matched analytical keywords)")
            intent = "ANALYTICAL"
            if pipeline == ["sql"]:
                pipeline = ["sql", "eda", "insight", "viz"]

    # Enforce a deterministic execution-mode token
    if execution_mode not in ("sql", "python"):
        execution_mode = "sql"

    # Pipeline normalisation: the first step must be a data-fetch step that
    # matches the chosen execution mode.
    pipeline = _normalise_pipeline(pipeline, execution_mode, intent)

    # On re-plan: adjust pipeline based on reflection feedback
    if is_replan:
        pipeline = _adjust_pipeline_for_reflection(
            pipeline, reflection_feedback, intent, execution_mode
        )
        replan_count += 1
        logger.info("adjusted pipeline for reflection: %s", pipeline)

    logger.info("exit intent=%s mode=%s pipeline=%s", intent, execution_mode, pipeline)

    return {
        "schema_info": schema_info,
        "enhanced_context": enhanced_context,
        "datasources": datasources,
        "intent": intent,
        "execution_mode": execution_mode,
        "pipeline": pipeline,
        "replan_count": replan_count,
        "current_agent": "orchestrator",
        "agent_steps": state.get("agent_steps", []) + ["orchestrator"],
    }


def _normalise_pipeline(pipeline: list, execution_mode: str, intent: str) -> list:
    """Ensure the first step matches ``execution_mode`` and is followed by sensible follow-ups."""
    valid = {"sql", "python", "eda", "insight", "viz"}
    pipeline = [step for step in pipeline if step in valid]

    # Replace whichever data-fetch step the LLM picked with the chosen mode.
    pipeline = [step for step in pipeline if step not in ("sql", "python")]
    pipeline.insert(0, execution_mode)

    if intent == "RETRIEVAL":
        return pipeline[:1]
    return pipeline


def _adjust_pipeline_for_reflection(
    pipeline: list, feedback: str, intent: str, execution_mode: str
) -> list:
    """Adjust pipeline based on reflection feedback.

    Parses feedback for missing elements and adds them to the pipeline.
    """
    feedback_lower = feedback.lower()

    # Add missing agents based on critique
    additions = []

    if "eda" in feedback_lower or "exploratory" in feedback_lower or "distribution" in feedback_lower:
        if "eda" not in pipeline:
            additions.append("eda")

    if "insight" in feedback_lower or "business" in feedback_lower or "actionable" in feedback_lower:
        if "insight" not in pipeline:
            additions.append("insight")

    if "viz" in feedback_lower or "chart" in feedback_lower or "visual" in feedback_lower:
        if "viz" not in pipeline:
            additions.append("viz")

    # Merge additions while preserving order
    for agent in additions:
        if agent not in pipeline:
            pipeline.append(agent)

    # Ensure pipeline starts with correct execution mode
    pipeline = _normalise_pipeline(pipeline, execution_mode, intent)

    return pipeline


def route_after_orchestrator(state: AgentState) -> str:
    pipeline = state.get("pipeline", [])
    if not pipeline:
        return "final_report"
    first = pipeline[0]
    if first == "sql":
        return "sql"
    if first == "python":
        return "python"
    if first in ("eda", "insight", "viz"):
        return first
    return "final_report"
