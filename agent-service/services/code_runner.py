"""HTTP client for the sandbox: code, sql, variable retrieval."""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import httpx

CODE_RUNNER_URL = os.getenv("CODE_RUNNER_URL", "http://sandbox:8001/").rstrip("/")


async def execute_code(python_code: str, session_id: str) -> Dict[str, Any]:
    """Execute Python code in the sandbox and return results."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{CODE_RUNNER_URL}/code",
                json={
                    "code": python_code.replace("\\", "%@"),
                    "id": session_id,
                },
            )
            response.raise_for_status()
            result = response.json()
            if "error" in result:
                return {"code_error": result["error"]}
            return {"ok": True}
    except Exception as exc:
        return {"error": str(exc)}


async def execute_sql(
    sql: str,
    session_id: str,
    result_variable: str = "df_result",
) -> Dict[str, Any]:
    """Execute SQL directly against the sandbox's DuckDB engine.

    The result is materialised as a pandas DataFrame under
    ``result_variable`` in the session, so visualisation/insight agents
    can reference it later by name.
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{CODE_RUNNER_URL}/sql",
                json={
                    "sql": sql,
                    "id": session_id,
                    "result_variable": result_variable,
                },
            )
            response.raise_for_status()
            result = response.json()
            if "error" in result:
                return {"code_error": result["error"], "sql": sql}
            return {
                "ok": True,
                "rows": result.get("rows", 0),
                "columns": result.get("columns", []),
                "preview": result.get("preview", []),
                "result_variable": result.get("result_variable", result_variable),
            }
    except Exception as exc:
        return {"error": str(exc)}


async def get_variable(session_id: str, var_name: str) -> Optional[Dict[str, Any]]:
    """Retrieve a variable from sandbox execution context."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                f"{CODE_RUNNER_URL}/var",
                json={"id": session_id, "name": var_name},
            )
            if response.status_code != 200:
                return None
            return response.json()
    except Exception as exc:
        print(f"[code_runner] get_variable failed: {exc}")
        return None


async def get_variable_results(session_id: str, var_names: List[str]) -> List[Dict[str, Any]]:
    """Retrieve multiple variables and return as content blocks."""
    content: List[Dict[str, Any]] = []
    for name in var_names:
        result = await get_variable(session_id, name)
        if result and "result" in result:
            for item in result["result"]:
                var_type = item.get("type", "string")
                data = item.get("data")
                if var_type == "image":
                    content.append({"type": "image", "base64": data})
                elif var_type == "table":
                    content.append({"type": "table", "table": data})
                else:
                    content.append({"type": "variable", "data": data})
    return content
