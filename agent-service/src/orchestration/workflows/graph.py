from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agents.analysis.eda import eda_agent_node
from agents.web_discover.node import web_discover_agent_node
from agents.analysis.final_report import final_report_node
from agents.analysis.insight import insight_agent_node
from agents.analysis.viz import viz_agent_node
from agents.executor.code_executor import code_executor_node
from agents.executor.python import python_agent_node
from agents.executor.sql import route_after_sql, sql_agent_node
from agents.planner.node import planner_node
from agents.planner.routing import route_after_planner
from agents.reflection.nodes import reflection_node, route_after_final_report
from agents.shared.state import AgentState
from orchestration.orchestrator.node import orchestrator_node
from utils.agent_logger import get_logger

logger = get_logger("graph")


def build_graph():
    """Build and compile the multi-agent analytics LangGraph with ReAct planner hub."""
    builder = StateGraph(AgentState)

    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("planner", planner_node)
    builder.add_node("sql", sql_agent_node)
    builder.add_node("code_executor", code_executor_node)
    builder.add_node("python", python_agent_node)
    builder.add_node("web_discover", web_discover_agent_node)
    builder.add_node("eda", eda_agent_node)
    builder.add_node("insight", insight_agent_node)
    builder.add_node("viz", viz_agent_node)
    builder.add_node("final_report", final_report_node)
    builder.add_node("reflection", reflection_node)

    builder.set_entry_point("orchestrator")
    builder.add_edge("orchestrator", "planner")

    builder.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "sql": "sql",
            "python": "python",
            "web_discover": "web_discover",
            "eda": "eda",
            "insight": "insight",
            "viz": "viz",
            "final_report": "final_report",
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
    builder.add_edge("reflection", END)

    checkpointer = MemorySaver()
    logger.info("LangGraph compiled (agent-patterns ReAct + Reflection)")
    return builder.compile(checkpointer=checkpointer)


compiled_graph = build_graph()
