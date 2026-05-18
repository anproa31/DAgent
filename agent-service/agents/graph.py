from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from agents.state import AgentState
from agents.orchestrator import orchestrator_node, route_after_orchestrator
from agents.sql_agent import sql_agent_node, route_after_sql
from agents.code_executor import code_executor_node, route_after_code_executor
from agents.eda_agent import eda_agent_node, route_after_eda
from agents.insight_agent import insight_agent_node, route_after_insight
from agents.viz_agent import viz_agent_node
from agents.final_report import final_report_node


def build_graph():
    """Build and compile the multi-agent analytics LangGraph."""
    builder = StateGraph(AgentState)

    # Register all nodes
    builder.add_node("orchestrator", orchestrator_node)
    builder.add_node("sql", sql_agent_node)
    builder.add_node("code_executor", code_executor_node)
    builder.add_node("eda", eda_agent_node)
    builder.add_node("insight", insight_agent_node)
    builder.add_node("viz", viz_agent_node)
    builder.add_node("final_report", final_report_node)

    # Entry point
    builder.set_entry_point("orchestrator")

    # Orchestrator → first agent in pipeline
    builder.add_conditional_edges(
        "orchestrator",
        route_after_orchestrator,
        {
            "sql": "sql",
            "eda": "eda",
            "insight": "insight",
            "viz": "viz",
            "final_report": "final_report",
        },
    )

    # SQL → approve/reject loop → code_executor
    builder.add_conditional_edges(
        "sql",
        route_after_sql,
        {
            "sql": "sql",  # loop back for regeneration after rejection
            "code_executor": "code_executor",
            "final_report": "final_report",
        },
    )

    # Code executor → EDA / insight / viz / final
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

    # EDA → insight / viz / final
    builder.add_conditional_edges(
        "eda",
        route_after_eda,
        {
            "insight": "insight",
            "viz": "viz",
            "final_report": "final_report",
        },
    )

    # Insight → viz / final
    builder.add_conditional_edges(
        "insight",
        route_after_insight,
        {
            "viz": "viz",
            "final_report": "final_report",
        },
    )

    # Viz → always goes to final_report
    builder.add_edge("viz", "final_report")

    # Final report → END
    builder.add_edge("final_report", END)

    # Use MemorySaver for HITL checkpointing (interrupt/resume)
    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)


# Module-level singleton
compiled_graph = build_graph()
