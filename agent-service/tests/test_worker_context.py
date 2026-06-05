"""Tests for worker scope isolation and guardrails."""

from agents.shared.worker_context import (
    build_worker_user_message,
    check_python_scope_violations,
    sanitize_eda_output,
    sanitize_sql_explanation,
)


def _base_state(**overrides):
    state = {
        "query": "Why are employees leaving? Analyze attrition and recommend actions.",
        "current_action": "sql",
        "execution_plan": [
            {
                "step_id": 1,
                "action": "sql",
                "status": "pending",
                "description": "Fetch data via DuckDB SQL against registered datasources",
                "rely": [],
            }
        ],
        "planner_history": [
            {
                "thought": "Need attrition data",
                "action": "exec",
                "action_input": {"task": "fetch employee attrition flags and departments"},
            }
        ],
    }
    state.update(overrides)
    return state


def test_build_worker_user_message_scopes_sql_task():
    msg = build_worker_user_message(_base_state(), "sql")
    assert "Assigned step" in msg
    assert "OUT OF SCOPE" in msg
    assert "fetch employee attrition flags" in msg
    assert "you must NOT" in msg.lower() or "do not" in msg.lower()


def test_sanitize_sql_explanation_strips_insights():
    raw = (
        "This query shows attrition drivers. We recommend focusing on Engineering. "
        "Key finding: high turnover."
    )
    cleaned = sanitize_sql_explanation(raw)
    assert "recommend" not in cleaned.lower()
    assert "key finding" not in cleaned.lower()


def test_check_python_scope_violations_detects_charts():
    code = "df_result = df.groupby('dept').size()\nplt.bar(df_result.index, df_result.values)"
    violations = check_python_scope_violations(code)
    assert "chart code" in violations[0]


def test_sanitize_eda_output_removes_recommendation_lines():
    raw = (
        "Shape: 100 rows.\n"
        "**Recommendation:** Focus on Engineering.\n"
        "Mean age is 34."
    )
    cleaned = sanitize_eda_output(raw)
    assert "Recommendation" not in cleaned
    assert "Mean age" in cleaned
