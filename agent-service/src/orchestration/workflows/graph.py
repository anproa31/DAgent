from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agents.analysis.eda import eda_agent_node
from agents.web_discover.node import web_discover_agent_node
from agents.analysis.final_report import final_report_node
from agents.analysis.insight import insight_agent_node
from agents.analysis.viz import viz_agent_node
from agents.executor.code_executor import code_executor_node
from agents.executor.exec_router import exec_decider_node, route_after_exec
from agents.executor.python import python_agent_node
from agents.executor.sql import route_after_sql, sql_agent_node
from agents.planner.node import planner_node
from agents.planner.routing import route_after_planner
from agents.reflection.nodes import (
    reflection_node,
    reflection_router,
    route_after_final_report,
)
from agents.shared.error_boundary import with_error_boundary
from agents.shared.state import AgentState
from orchestration.orchestrator.node import orchestrator_node
from utils.agent_logger import get_logger

logger = get_logger("graph")


def build_graph():
    """Build the orchestrator-worker LangGraph (diagram #1) with agent loop (diagram #2).

    User → Orchestrator (reason/plan) → Planner hub (perceive/brain/route)
         → Specialized agents (scope/knowledge/tools: act/observe) → Report → Reflection
    """
    builder = StateGraph(AgentState)

    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("planner", planner_node)
    # Workers run inside an error boundary so a crash/timeout becomes an error
    # observation the planner can react to, rather than aborting the run
    # (solution.md §9). HITL nodes (sql/python/web_discover) pass timeout=None
    # so the interrupt control-flow signal is never wrapped or clipped.
    # exec decides SQL vs Python at runtime, then routes to the matching worker.
    builder.add_node("exec", with_error_boundary(exec_decider_node, "exec"))
    builder.add_node("sql", with_error_boundary(sql_agent_node, "sql", timeout=None))
    builder.add_node("code_executor", with_error_boundary(code_executor_node, "code_executor"))
    builder.add_node("python", with_error_boundary(python_agent_node, "python", timeout=None))
    builder.add_node("web_discover", with_error_boundary(web_discover_agent_node, "web_discover", timeout=None))
    builder.add_node("eda", with_error_boundary(eda_agent_node, "eda"))
    builder.add_node("insight", with_error_boundary(insight_agent_node, "insight"))
    builder.add_node("viz", with_error_boundary(viz_agent_node, "viz"))
    builder.add_node("final_report", final_report_node)
    builder.add_node("reflection", reflection_node)

    builder.set_entry_point("orchestrator")
    builder.add_edge("orchestrator", "planner")

    builder.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "exec": "exec",
            "sql": "sql",
            "python": "python",
            "web_discover": "web_discover",
            "eda": "eda",
            "insight": "insight",
            "viz": "viz",
            "final_report": "final_report",
        },
    )

    # exec → sql | python based on the runtime tool decision.
    builder.add_conditional_edges(
        "exec",
        route_after_exec,
        {
            "sql": "sql",
            "python": "python",
        },
    )

    builder.add_conditional_edges(
        "sql",
        route_after_sql,
        {
            "code_executor": "code_executor",
            "planner": "planner",
        },
    )
    builder.add_edge("code_executor", "planner")
    builder.add_edge("web_discover", "planner")
    builder.add_edge("python", "planner")
    builder.add_edge("eda", "planner")
    builder.add_edge("insight", "planner")
    builder.add_edge("viz", "planner")

    builder.add_conditional_edges(
        "final_report",
        route_after_final_report,
        {"reflection": "reflection", "done": END},
    )
    # Reflection may request one targeted rerun back through the planner when it
    # finds a defect text-refinement can't fix (solution.md §2 Fix 3).
    builder.add_conditional_edges(
        "reflection",
        reflection_router,
        {"planner": "planner", "done": END},
    )

    checkpointer = MemorySaver()
    logger.info("LangGraph compiled (agent-patterns ReAct + Reflection)")
    return builder.compile(checkpointer=checkpointer)


compiled_graph = build_graph()
