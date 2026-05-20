"""HTTP client for the sandbox (code runner) service."""
from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from ...core.config import Settings, get_settings


class SandboxClient:
    """Async HTTP adapter for sandbox code execution and datasource sync."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings or get_settings()

    def _url(self, path: str) -> str:
        return f"{self._settings.sandbox_url}{path}"

    @property
    def base_url(self) -> str:
        return self._settings.sandbox_url

    async def execute_code(self, python_code: str, access_id: str) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self._url("/code"),
                    json={
                        "code": python_code.replace("\\", "%@"),
                        "id": access_id,
                    },
                )
            response.raise_for_status()
            runner_result = response.json()
            if "error" in runner_result:
                return {"code_error": runner_result["error"]}
            return {"result": runner_result}
        except httpx.HTTPStatusError:
            return {"error": "HTTP connection error during code execution"}
        except httpx.TimeoutException:
            return {"error": "Request timed out error during code execution"}
        except Exception:
            return {"error": "An unexpected error during code execution"}

    async def rollback(self, access_id: str) -> Dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self._url("/rollback"),
                    json={"id": access_id},
                )
            response.raise_for_status()
            rollback_result = response.json()
            if "error" in rollback_result:
                return {"error": rollback_result["error"]}
            return {"result": rollback_result}
        except httpx.HTTPStatusError:
            return {"error": "HTTP connection error during rollback"}
        except httpx.TimeoutException:
            return {"error": "Request timed out error during rollback"}
        except Exception:
            return {"error": "An unexpected error during rollback"}

    async def get_variable(self, access_id: str, variable_name: str) -> Optional[Dict[str, Any]]:
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self._url("/var"),
                    json={"id": access_id, "name": variable_name},
                )
            if response.status_code != 200:
                return None
            return response.json()
        except Exception:
            return None

    async def register_datasource(self, payload: Dict[str, Any]) -> None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self._url("/register-datasource"),
                json=payload,
            )
            response.raise_for_status()

    async def unregister_datasource(self, datasource_id: str, view_names: list[str]) -> None:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self._url("/unregister-datasource"),
                json={"datasource_id": datasource_id, "view_names": view_names},
            )
            response.raise_for_status()

    async def run_sql(
        self,
        sql: str,
        session_id: str,
        *,
        result_variable: str = "_preview_df",
        preview_limit: int = 20,
    ) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self._url("/sql"),
                json={
                    "sql": sql,
                    "id": session_id,
                    "result_variable": result_variable,
                    "preview_limit": preview_limit,
                },
            )
        payload = response.json() if response.content else {}
        if response.status_code != 200:
            payload.setdefault(
                "error", f"Preview failed (status {response.status_code})"
            )
        return payload
