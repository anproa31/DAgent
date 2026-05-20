"""Convert control-layer results to legacy HTTP response bodies."""
from __future__ import annotations

from typing import Any, Dict

from execution_layer.base import ExecutionResult, ExecutionStatus


def to_http_response(result: ExecutionResult) -> Dict[str, Any]:
    if result.status == ExecutionStatus.SUCCESS:
        if result.payload:
            return dict(result.payload)
        if result.output:
            return {"ok": result.output}
        return {"ok": True}

    response: Dict[str, Any] = {"error": result.error or result.output or "Execution failed"}
    if "trace" in result.payload:
        response["trace"] = result.payload["trace"]
    if "id" in result.payload:
        response["id"] = result.payload["id"]
    if "sql" in result.payload:
        response["sql"] = result.payload["sql"]
    return response
