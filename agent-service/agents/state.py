from typing import Any, Dict, List, TypedDict


class AgentState(TypedDict, total=False):
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
    datasources: List[Dict[str, Any]]  # structured list from /internal/datasources

    # Orchestrator decision
    intent: str  # "RETRIEVAL" or "ANALYTICAL"
    pipeline: List[str]  # e.g. ["sql", "eda", "insight", "viz"]
    execution_mode: str  # "sql" | "python" — chosen by orchestrator
    current_agent: str
    agent_steps: List[str]

    # SQL Agent outputs
    sql_draft: str
    sql_explanation: str
    sql_approved: bool
    sql_rejection_reason: str

    # Python code for sandbox (used in execution_mode == "python")
    python_code: str

    # Sandbox execution outputs
    data_summary: str
    result_var_names: List[str]

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
