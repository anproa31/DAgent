import os
import httpx
from typing import Optional

CODE_RUNNER_URL = os.getenv("CODE_RUNNER_URL", "http://data-analysis-agent-sandbox:8001/")


async def execute_code(python_code: str, session_id: str) -> dict:
    """Execute Python code in the sandbox and return results."""
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                CODE_RUNNER_URL + "code",
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
    except Exception as e:
        return {"error": str(e)}


async def get_variable(session_id: str, var_name: str) -> Optional[dict]:
    """Retrieve a variable from sandbox execution context."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                CODE_RUNNER_URL + "var",
                json={"id": session_id, "name": var_name},
            )
            if response.status_code != 200:
                return None
            return response.json()
    except Exception as e:
        print(f"[code_runner] get_variable failed: {e}")
        return None


async def get_variable_results(session_id: str, var_names: list) -> list:
    """Retrieve multiple variables and return as content blocks."""
    content = []
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
