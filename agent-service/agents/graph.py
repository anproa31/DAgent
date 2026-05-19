from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from agents.code_executor import code_executor_node, route_after_code_executor
from agents.eda_agent import eda_agent_node, route_after_eda
from agents.final_report import final_report_node
from agents.insight_agent import insight_agent_node, route_after_insight
from agents.orchestrator import orchestrator_node, route_after_orchestrator
from agents.python_agent import python_agent_node, route_after_python
from agents.sql_agent import route_after_sql, sql_agent_node
from agents.state import AgentState
from agents.viz_agent import viz_agent_node


def build_graph():
    """Build and compile the multi-agent analytics LangGraph."""
    builder = StateGraph(AgentState)

    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("sql", sql_agent_node)
    builder.add_node("code_executor", code_executor_node)
    builder.add_node("python", python_agent_node)
    builder.add_node("eda", eda_agent_node)
    builder.add_node("insight", insight_agent_node)
    builder.add_node("viz", viz_agent_node)
    builder.add_node("final_report", final_report_node)

    builder.set_entry_point("orchestrator")

    builder.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {
            "sql": "sql",
            "python": "python",
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
            "sql": "sql",
            "code_executor": "code_executor",
            "final_report": "final_report",
        },
    )

    builder.add_conditional_edges(
        "code_executor",
        route_after_code_executor,
        {
            "eda": "eda",
            "insight": "insight",
            "viz": "viz",
            "final_report": "final_report",
        },
    )

    builder.add_conditional_edges(
        "python",
        route_after_python,
        {
            "eda": "eda",
            "insight": "insight",
            "viz": "viz",
            "final_report": "final_report",
        },
    )

    builder.add_conditional_edges(
        "eda",
        route_after_eda,
        {
            "insight": "insight",
            "viz": "viz",
            "final_report": "final_report",
        },
    )

    builder.add_conditional_edges(
        "insight",
        route_after_insight,
        {
            "viz": "viz",
            "final_report": "final_report",
        },
    )

    builder.add_edge("viz", "final_report")
    builder.add_edge("final_report", END)

    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)


# Module-level singleton
compiled_graph = build_graph()
