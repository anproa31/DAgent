"""Analytics adapter for agent-patterns ReActAgent (planning only)."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple

from agent_patterns.patterns import ReActAgent
from langchain_openai import ChatOpenAI

from agents.planner.plan_tracker import resolve_planner_action
from agents.shared.llm_endpoint import normalize_base_url
from agents.shared.state import AgentState, PlannerStep
from agents.shared.web_discover_policy import should_use_discover_action

MAX_PLANNER_STEPS = 15

ANALYTICS_REACT_INSTRUCTIONS = """
You are a data analytics ReAct planner. Choose ONE tool per step.

Available tools:
- sql — generate/execute SQL against registered datasources
- python — pandas/numpy/scipy analysis in sandbox
- discover_data — web data discovery (only when allowed)
- eda — exploratory data analysis on df_result
- insight — business narrative from data/EDA
- viz — matplotlib charts
- generate_result — compile final report when the query is answered

Respond using this exact format:
Thought: <why this tool is needed given observations>
Action: <tool name>
Action Input: <optional JSON or brief note>

Use Action: generate_result when data and analysis already answer the query.
Do NOT call eda/insight/viz for simple RETRIEVAL unless explicitly needed.
"""

THOUGHT_STEP_USER = """Task context:
{input}

Previous steps:
{history}

Available tools: {available_tools}

Decide the next single tool to call."""


class AnalyticsReActAgent(ReActAgent):
    """ReActAgent used for one planning step per graph iteration (workers run externally)."""

    VALID_ACTIONS = {
        "sql",
        "python",
        "discover_data",
        "eda",
        "insight",
        "viz",
        "generate_result",
        "finish",
    }

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        max_iterations: int = MAX_PLANNER_STEPS,
    ):
        self._endpoint_base_url = base_url
        self._endpoint_api_key = api_key or "none"
        self._endpoint_model = model

        llm_configs = {
            "thinking": {
                "provider": "openai",
                "model_name": model,
                "temperature": 0.1,
            },
        }

        super().__init__(
            llm_configs=llm_configs,
            tools={},
            max_iterations=max_iterations,
            custom_instructions=ANALYTICS_REACT_INSTRUCTIONS,
            prompt_overrides={
                "ThoughtStep": {
                    "user": THOUGHT_STEP_USER,
                },
            },
        )

    def _get_llm(self, role: str):
        if role in self._llm_cache:
            return self._llm_cache[role]

        config = self.llm_configs[role]
        llm = ChatOpenAI(
            model=config["model_name"],
            temperature=config.get("temperature", 0.1),
            max_tokens=config.get("max_tokens", 4000),
            base_url=normalize_base_url(self._endpoint_base_url),
            api_key=self._endpoint_api_key,
        )
        self._llm_cache[role] = llm
        return llm

    def run(self, input_data: str) -> str:
        raise NotImplementedError(
            "Use plan_next() — worker tools execute in external LangGraph nodes."
        )

    def plan_next(self, state: AgentState, *, task_context: str) -> Dict[str, Any]:
        """Run one ReAct thought step and return a planner decision."""
        iteration = state.get("planner_step_index", 0)
        if iteration >= self.max_iterations:
            return {
                "thought": f"Max steps ({self.max_iterations}) reached — generating report.",
                "action": "generate_result",
                "action_input": {},
            }

        react_state = {
            "input": task_context,
            "thought": "",
            "action": {},
            "observation": None,
            "intermediate_steps": _history_to_intermediate_steps(state.get("planner_history", [])),
            "iteration_count": iteration,
            "max_iterations": self.max_iterations,
        }

        updated = self._generate_thought_and_action(react_state)
        thought = updated.get("thought", "")
        raw_action = updated.get("action", {})
        action = _normalize_tool_name(raw_action.get("tool_name", ""))
        action_input = _parse_action_input(raw_action.get("tool_input", ""))

        discover_allowed, discover_reason = should_use_discover_action(state)
        if action == "discover_data" and not discover_allowed:
            action = "sql"
            thought = f"{thought} [discover_data blocked: {discover_reason}. Using sql.]".strip()

        if action not in self.VALID_ACTIONS:
            action = "sql"
            thought = f"{thought} [invalid action normalized to sql]".strip()

        last_observation = state.get("last_observation") or {}
        execution_plan = state.get("execution_plan") or []
        action, plan_note = resolve_planner_action(
            state,
            action,
            last_observation=last_observation,
        )
        if plan_note and plan_note not in thought:
            thought = f"{thought} [{plan_note}]".strip()

        return {
            "thought": thought,
            "action": action,
            "action_input": action_input,
        }


_agent_cache: Dict[str, AnalyticsReActAgent] = {}


def get_analytics_react_agent(
    *,
    base_url: str,
    api_key: str,
    model: str,
    max_iterations: int = MAX_PLANNER_STEPS,
) -> AnalyticsReActAgent:
    key = f"{base_url}|{api_key}|{model}|{max_iterations}"
    agent = _agent_cache.get(key)
    if agent is None:
        agent = AnalyticsReActAgent(
            base_url=base_url,
            api_key=api_key,
            model=model,
            max_iterations=max_iterations,
        )
        _agent_cache[key] = agent
    return agent


def _history_to_intermediate_steps(history: List[PlannerStep]) -> List[Tuple[str, Dict[str, Any], str]]:
    steps: List[Tuple[str, Dict[str, Any], str]] = []
    for step in history:
        thought = step.get("thought", "")
        action_name = step.get("action", "")
        action = {
            "tool_name": action_name,
            "tool_input": json.dumps(step.get("action_input") or {}),
        }
        observation = step.get("observation") or {}
        obs_text = observation.get("summary") or json.dumps(observation)[:500] or "(pending)"
        steps.append((thought, action, obs_text))
    return steps


def _normalize_tool_name(tool_name: str) -> str:
    normalized = (tool_name or "").strip().lower().replace(" ", "_")
    aliases = {
        "final_answer": "generate_result",
        "final": "generate_result",
        "finish": "generate_result",
        "web_discover": "discover_data",
    }
    return aliases.get(normalized, normalized or "sql")


def _parse_action_input(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    text = str(raw).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return {"note": text}
