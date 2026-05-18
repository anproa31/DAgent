from typing import TypedDict, List, Optional, Any


class AgentState(TypedDict):
    # Identity
    session_id: str
    run_id: str

    # User inputs
    query: str
    tables: List[str]
    model: str
    base_url: str
    api_key: str

    # Schema context
    schema_info: str

    # Orchestrator decision
    intent: str  # "RETRIEVAL" or "ANALYTICAL"
    pipeline: List[str]  # e.g. ["sql", "eda", "insight", "viz"]
    current_agent: str
    agent_steps: List[str]  # history of completed agent names

    # SQL Agent outputs
    sql_draft: str
    sql_explanation: str
    sql_approved: bool
    sql_rejection_reason: str

    # Python code for sandbox
    python_code: str

    # Sandbox execution outputs
    data_summary: str       # text summary of query results
    result_var_names: List[str]  # variable names to retrieve from sandbox

    # EDA Agent outputs
    eda_summary: str

    # Insight Agent outputs
    insights: str

    # Visualization Agent outputs
    viz_code: str
    viz_var_names: List[str]

    # Final compiled report
    report_content: List[Any]

    # Control
    done: bool
    error: str
