import re
import pandas as pd
from agents.state import AgentState
from services.code_runner import execute_code, get_variable


_EXEC_PYTHON_TEMPLATE = '''\
import pandas as pd
import numpy as np

sql = """{sql}"""
try:
    df_result = pd.read_sql_query(sql, con=engine)
    print(f"Query returned {{len(df_result)}} rows, {{len(df_result.columns)}} columns")
except Exception as e:
    df_result = pd.DataFrame()
    error_message = str(e)
    print(f"SQL execution error: {{e}}")
'''


async def code_executor_node(state: AgentState) -> dict:
    """Execute the approved SQL via the sandbox and capture results."""
    sql = state.get("sql_draft", "")
    session_id = state.get("session_id", state.get("run_id", "default"))

    print(f"[code_executor] executing SQL in sandbox, session={session_id}")

    python_code = _EXEC_PYTHON_TEMPLATE.format(sql=sql.replace('"', '\\"'))

    result = await execute_code(python_code, session_id)
    if "code_error" in result or "error" in result:
        err = result.get("code_error") or result.get("error")
        return {
            "current_agent": "code_executor",
            "python_code": python_code,
            "data_summary": f"Execution error: {err}",
            "result_var_names": [],
            "agent_steps": state.get("agent_steps", []) + ["code_executor"],
            "error": f"Code execution error: {err}",
        }

    # Retrieve df_result variable to build a data summary
    df_var = await get_variable(session_id, "df_result")
    data_summary = _build_data_summary(df_var)

    return {
        "current_agent": "code_executor",
        "python_code": python_code,
        "data_summary": data_summary,
        "result_var_names": ["df_result"],
        "agent_steps": state.get("agent_steps", []) + ["code_executor"],
    }


def _build_data_summary(df_var: dict) -> str:
    """Convert sandbox df variable to a concise text summary for LLM context."""
    if not df_var or "result" not in df_var:
        return "No data returned"
    try:
        items = df_var["result"]
        if not items:
            return "Empty result set"
        # Find first table item
        for item in items:
            if item.get("type") == "table":
                import json
                rows = json.loads(item["data"])
                if not rows:
                    return "Empty table result"
                columns = list(rows[0].keys())
                row_count = len(rows)
                # Build preview (first 5 rows)
                preview_lines = [" | ".join(str(r.get(c, "")) for c in columns) for r in rows[:5]]
                header = " | ".join(columns)
                return (
                    f"Columns: {columns}\n"
                    f"Row count: {row_count}\n"
                    f"Preview ({min(5, row_count)} rows):\n"
                    f"{header}\n" + "\n".join(preview_lines)
                )
        return "Result available but no table data"
    except Exception as e:
        return f"Data summary unavailable: {e}"


def route_after_code_executor(state: AgentState) -> str:
    pipeline = state.get("pipeline", [])
    if state.get("error"):
        return "final_report"
    remaining = [a for a in pipeline if a not in ("sql",)]
    if "eda" in remaining:
        return "eda"
    if "insight" in remaining:
        return "insight"
    if "viz" in remaining:
        return "viz"
    return "final_report"
