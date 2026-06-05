from typing import Any, Dict, List, TypedDict, Optional


class PlannerStep(TypedDict, total=False):
    """Single ReAct planner step."""
    thought: str
    action: str
    action_input: Dict[str, Any]
    observation: Dict[str, Any]


class ExecutionPlanStep(TypedDict, total=False):
    """Structured plan step (DB-GPT GptsPlan-inspired)."""
    step_id: int
    action: str
    status: str  # pending | running | done | failed | skipped
    description: str
    rely: List[int]


class AgentState(TypedDict, total=False):
    # Identity
    session_id: str
    run_id: str

    # User inputs
    query: str
    language: str  # ISO 639-1 code for user-facing responses (e.g. vi, en)
    tables: List[str]
    model: str
    base_url: str
    api_key: str

    # Memory selection (composer @ / pickers) + embedding override (Settings UI)
    kb_documents: List[str]   # KB document names to scope semantic recall to (@)
    skill_ids: List[str]      # procedural skill ids to force-include (/)
    embedding_base_url: str   # per-request embedding endpoint override
    embedding_model: str

    # Schema context
    schema_info: str
    enhanced_context: str  # query-focused semantic context from context-engine /enhance (or fallback)
    datasources: List[Dict[str, Any]]  # structured list from /internal/datasources

    # Planner decision (ReAct)
    intent: str  # "RETRIEVAL" or "ANALYTICAL"
    execution_mode: str  # "sql" | "python" — chosen by planner
    current_agent: str
    agent_steps: List[str]

    # ReAct planner state
    planner_history: List[PlannerStep]  # ordered trace of thought/action/observation
    last_observation: Dict[str, Any]  # structured summary of most recent agent run
    current_action: str  # action chosen for current step
    planner_step_index: int  # current step count
    completed_actions: List[str]  # actions already executed in this run

    # Structured execution plan (orchestrator → planner contract)
    execution_plan: List[ExecutionPlanStep]
    orchestration_mode: str  # FIXED | AUTO_PLAN | EXPLORE

    # Pipeline summary (mirrors worker steps in execution_plan)
    pipeline: List[str]

    # SQL Agent outputs
    sql_draft: str
    sql_explanation: str
    sql_approved: bool
    sql_rejection_reason: str

    # Web discover HITL
    web_discover_proposal: Dict[str, Any]
    web_discover_approved: bool
    web_discover_rejection_reason: str

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

    # Agent-patterns Reflection (generate → reflect → refine)
    reflection_cycle: int
    max_reflection_cycles: int
    reflection: str
    refined_output: str
    needs_refinement: bool
    continue_reflection: bool

    # Reflection → planner targeted rerun (solution.md §2 Fix 3)
    reflection_needs_rerun: bool
    rerun_count: int

    # Python HITL risk tier (solution.md §5)
    python_risk: str  # safe | medium | high

    # Control
    done: bool
    error: str
    completion_reason: str  # success | step_limit | hitl_timeout | user_cancelled
