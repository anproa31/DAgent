"""Specialized agent registry: scope & instructions, knowledge, tools.

Each worker agent is defined with the three properties from the orchestrator-worker diagram.
The user-facing API talks only to the Orchestrator; workers are invoked via routing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional

# Scope text is sourced from worker_context._SCOPE — re-exported here for the registry.
from agents.shared.worker_context import _SCOPE, _ROLE_ALIASES


@dataclass(frozen=True)
class SpecializedAgentDef:
    """One specialized agent: scope, knowledge sources, and allowed tools."""

    role: str
    graph_node: str
    step_title: str
    deliverable: str
    forbidden: str
    knowledge_sources: FrozenSet[str]
    tools: FrozenSet[str]
    description: str = ""


_KNOWLEDGE_SHARED = frozenset(
    {"schema_info", "enhanced_context", "datasources", "execution_plan", "planner_history"}
)
_KNOWLEDGE_ANALYSIS = _KNOWLEDGE_SHARED | frozenset(
    {"data_summary", "result_var_names", "eda_summary", "kb_documents", "skill_ids"}
)


def _scope(role: str) -> Dict[str, str]:
    return _SCOPE.get(role, {})


SPECIALIZED_AGENTS: Dict[str, SpecializedAgentDef] = {
    "exec": SpecializedAgentDef(
        role="exec",
        graph_node="exec",
        step_title="Choose SQL or Python runtime",
        deliverable="Decide whether SQL or Python is the right runtime for the data step.",
        forbidden="Do NOT generate business insights or final answers.",
        knowledge_sources=_KNOWLEDGE_SHARED,
        tools=frozenset(),
        description="Runtime router — dispatches to sql or python worker.",
    ),
    "sql": SpecializedAgentDef(
        role="sql",
        graph_node="sql",
        step_title=_scope("sql").get("step_title", "Fetch data via SQL"),
        deliverable=_scope("sql").get("deliverable", ""),
        forbidden=_scope("sql").get("forbidden", ""),
        knowledge_sources=_KNOWLEDGE_SHARED | frozenset({"kb_documents", "skill_ids"}),
        tools=frozenset({"execute_sql"}),
        description="Generates DuckDB SQL and requests HITL approval.",
    ),
    "code_executor": SpecializedAgentDef(
        role="code_executor",
        graph_node="code_executor",
        step_title="Execute approved SQL",
        deliverable="Run the approved SQL query in the sandbox.",
        forbidden="Do NOT modify SQL or write insights.",
        knowledge_sources=frozenset({"sql_draft", "session_id"}),
        tools=frozenset({"execute_sql", "get_variable", "get_variables"}),
        description="Executes user-approved SQL in the sandbox.",
    ),
    "python": SpecializedAgentDef(
        role="python",
        graph_node="python",
        step_title=_scope("python").get("step_title", "Compute via Python"),
        deliverable=_scope("python").get("deliverable", ""),
        forbidden=_scope("python").get("forbidden", ""),
        knowledge_sources=_KNOWLEDGE_SHARED | frozenset({"kb_documents", "skill_ids"}),
        tools=frozenset({"execute_python", "get_variable", "get_variables", "rollback"}),
        description="Generates and executes Python in the sandbox.",
    ),
    "web_discover": SpecializedAgentDef(
        role="web_discover",
        graph_node="web_discover",
        step_title="Discover external data",
        deliverable="Propose and register web datasets when local schema is insufficient.",
        forbidden="Do NOT answer the user query directly.",
        knowledge_sources=_KNOWLEDGE_SHARED,
        tools=frozenset(
            {"discover_web_data", "propose_web_data", "register_web_data", "fetch_web_data"}
        ),
        description="Web data discovery with HITL approval.",
    ),
    "eda": SpecializedAgentDef(
        role="eda",
        graph_node="eda",
        step_title=_scope("eda").get("step_title", "Exploratory data analysis"),
        deliverable=_scope("eda").get("deliverable", ""),
        forbidden=_scope("eda").get("forbidden", ""),
        knowledge_sources=_KNOWLEDGE_ANALYSIS,
        tools=frozenset(),
        description="LLM-only EDA narrative from df_result.",
    ),
    "insight": SpecializedAgentDef(
        role="insight",
        graph_node="insight",
        step_title=_scope("insight").get("step_title", "Business insights"),
        deliverable=_scope("insight").get("deliverable", ""),
        forbidden=_scope("insight").get("forbidden", ""),
        knowledge_sources=_KNOWLEDGE_ANALYSIS,
        tools=frozenset(),
        description="LLM-only business insight narrative.",
    ),
    "viz": SpecializedAgentDef(
        role="viz",
        graph_node="viz",
        step_title=_scope("viz").get("step_title", "Data visualization"),
        deliverable=_scope("viz").get("deliverable", ""),
        forbidden=_scope("viz").get("forbidden", ""),
        knowledge_sources=_KNOWLEDGE_ANALYSIS,
        tools=frozenset({"execute_python"}),
        description="Generates matplotlib code and executes charts in sandbox.",
    ),
    "final_report": SpecializedAgentDef(
        role="final_report",
        graph_node="final_report",
        step_title="Compile final report",
        deliverable="Structured report blocks answering the user query.",
        forbidden="Do NOT fetch new data or run sandbox tools.",
        knowledge_sources=_KNOWLEDGE_ANALYSIS
        | frozenset({"insights", "viz_var_names", "report_content"}),
        tools=frozenset(),
        description="Compiles artifacts into the user-facing report.",
    ),
    "reflection": SpecializedAgentDef(
        role="reflection",
        graph_node="reflection",
        step_title="Reflect on report quality",
        deliverable="Critique and refine the compiled report.",
        forbidden="Do NOT re-fetch data unless requesting a targeted rerun.",
        knowledge_sources=frozenset({"report_content", "planner_history", "query"}),
        tools=frozenset(),
        description="Post-report reflection and optional targeted rerun.",
    ),
}

# Planner action names → graph node / agent role
PLANNER_ACTION_TO_AGENT: Dict[str, str] = {
    "exec": "exec",
    "sql": "sql",
    "python": "python",
    "discover_data": "web_discover",
    "eda": "eda",
    "insight": "insight",
    "viz": "viz",
    "generate_result": "final_report",
    "finish": "final_report",
}


def get_agent_def(role: str) -> Optional[SpecializedAgentDef]:
    """Resolve agent definition by role or planner action alias."""
    role = _ROLE_ALIASES.get(role, role)
    mapped = PLANNER_ACTION_TO_AGENT.get(role, role)
    return SPECIALIZED_AGENTS.get(mapped)


def is_tool_allowed(role: str, tool_name: str) -> bool:
    """Scope check: may this agent invoke this tool?"""
    agent = get_agent_def(role)
    if agent is None:
        return True
    if not agent.tools:
        return False
    return tool_name in agent.tools


def build_knowledge_slice(state: dict, role: str) -> Dict[str, object]:
    """Extract only the knowledge fields this agent is allowed to see."""
    agent = get_agent_def(role)
    if agent is None:
        return {}
    return {key: state.get(key) for key in agent.knowledge_sources if key in state}


def list_specialized_agents() -> List[SpecializedAgentDef]:
    return list(SPECIALIZED_AGENTS.values())
