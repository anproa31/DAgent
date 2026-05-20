"""Backward-compatible wrapper around SandboxClient."""
from __future__ import annotations

from typing import Any, Dict, Optional

from .infrastructure.external.sandbox_client import SandboxClient
from .models.requests import VariableRetrievalResponse


class CodeService:
    def __init__(self, sandbox: Optional[SandboxClient] = None) -> None:
        self._sandbox = sandbox or SandboxClient()

    async def code_execution(self, python_code: str, access_id: str) -> Dict[str, Any]:
        return await self._sandbox.execute_code(python_code, access_id)

    async def code_rollback(self, access_id: str) -> Dict[str, Any]:
        return await self._sandbox.rollback(access_id)

    async def get_variable(self, request: VariableRetrievalResponse) -> Dict[str, Any]:
        result = await self._sandbox.get_variable(request.id, request.name)
        if result is None:
            return {"error": "Request failed"}
        return result

    async def get_variable_value(
        self, analysis_id: str, variable_name: str
    ) -> Optional[Dict[str, Any]]:
        return await self._sandbox.get_variable(analysis_id, variable_name)
