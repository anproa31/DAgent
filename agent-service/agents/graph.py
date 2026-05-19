from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agents.code_executor import code_executor_node
from agents.eda_agent import eda_agent_node
from agents.final_report import final_report_node
from agents.insight_agent import insight_agent_node
from agents.orchestrator import orchestrator_node
from agents.planner import planner_node, route_after_planner, create_observation
from agents.python_agent import python_agent_node
from agents.reflection_agent import reflection_agent_node, route_after_reflection
from agents.sql_agent import sql_agent_node, route_after_sql
from agents.state import AgentState
from agents.viz_agent import viz_agent_node
from utils.agent_logger import get_logger

logger = get_logger("graph")


def build_graph():
    """Build and compile the multi-agent analytics LangGraph with ReAct planner hub.

    Topology: Hub-and-spoke through planner. All specialized agents return to planner.
    """
    builder = StateGraph(AgentState)

    # Nodes
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("planner", planner_node)
    builder.add_node("sql", sql_agent_node)
    builder.add_node("code_executor", code_executor_node)
    builder.add_node("python", python_agent_node)
    builder.add_node("eda", eda_agent_node)
    builder.add_node("insight", insight_agent_node)
    builder.add_node("viz", viz_agent_node)
    builder.add_node("reflection", reflection_agent_node)
    builder.add_node("final_report", final_report_node)

    # Entry point: orchestrator does initial setup, then hands to planner
    builder.set_entry_point("orchestrator")
    builder.add_edge("orchestrator", "planner")

    # Planner routes to specialized agents
    builder.add_conditional_edges(
        "planner",
        route_after_planner,
        {
            "sql": "sql",
            "python": "python",
            "eda": "eda",
            "insight": "insight",
            "viz": "viz",
            "final_report": "final_report",
        },
    )

    # SQL HITL loop: conditional routing based on approval
    builder.add_conditional_edges(
        "sql",
        route_after_sql,
        {
            "code_executor": "code_executor",  # approved → execute
            "planner": "planner",  # rejected → re-plan
        },
    )
    builder.add_edge("code_executor", "planner")

    # All other agents return directly to planner
    builder.add_edge("python", "planner")
    builder.add_edge("eda", "planner")
    builder.add_edge("insight", "planner")
    builder.add_edge("viz", "planner")

    # Final report → reflection
    builder.add_edge("final_report", "reflection")

    # Reflection routes: pass → END, fail → planner (re-plan)
    builder.add_conditional_edges(
        "reflection",
        route_after_reflection,
        {
            "final_report": END,  # passed → done
            "planner": "planner",  # failed → re-plan via planner
        },
    )

    checkpointer = MemorySaver()
    logger.info("LangGraph compiled (planner hub topology)")
    return builder.compile(checkpointer=checkpointer)


# Module-level singleton
compiled_graph = build_graph()
