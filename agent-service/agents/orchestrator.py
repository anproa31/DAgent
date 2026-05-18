import json
import re
from agents.state import AgentState
from utils.llm_client import get_async_client, chat_complete
from utils.prompts import ORCHESTRATOR_SYSTEM
from services.schema_service import get_schema


async def orchestrator_node(state: AgentState) -> dict:
    """Analyse the query, fetch schema, and decide which pipeline to run."""
    print(f"[orchestrator] query={state['query'][:80]}")

    # Fetch schema if not already present
    schema_info = state.get("schema_info", "")
    if not schema_info:
        schema_info = await get_schema(state.get("tables"))

    client = get_async_client(state.get("base_url", ""), state.get("api_key", ""))
    model = state.get("model", "")

    messages = [
        {"role": "system", "content": ORCHESTRATOR_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Database schema:\n{schema_info}\n\n"
                f"User query: {state['query']}"
            ),
        },
    ]

    try:
        raw = await chat_complete(client, model, messages, temperature=0.1)
        # Extract JSON from response (handle markdown fences)
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        if json_match:
            decision = json.loads(json_match.group())
            intent = decision.get("intent", "ANALYTICAL").upper()
            pipeline = decision.get("pipeline", ["sql", "insight"])
        else:
            intent = "ANALYTICAL"
            pipeline = ["sql", "eda", "insight", "viz"]
    except Exception as e:
        print(f"[orchestrator] LLM error, using default pipeline: {e}")
        intent = "ANALYTICAL"
        pipeline = ["sql", "eda", "insight", "viz"]

    # Enforce pipeline constraints based on intent
    if intent == "RETRIEVAL":
        pipeline = ["sql"]
        print(f"[orchestrator] RETRIEVAL intent detected — lightweight pipeline")
    else:
        print(f"[orchestrator] ANALYTICAL intent — full pipeline: {pipeline}")

    return {
        "schema_info": schema_info,
        "intent": intent,
        "pipeline": pipeline,
        "current_agent": "orchestrator",
        "agent_steps": state.get("agent_steps", []) + ["orchestrator"],
    }


def route_after_orchestrator(state: AgentState) -> str:
    """Route to the first agent in the pipeline."""
    pipeline = state.get("pipeline", [])
    if not pipeline:
        return "final_report"
    first = pipeline[0]
    return first if first in ("sql", "eda", "insight", "viz") else "final_report"
