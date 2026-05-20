"""Code, SQL, and variable execution HTTP routes."""
from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter

from api.schemas import (
    CodeExecutionRequest,
    SQLExecutionRequest,
    VariableRetrievalRequest,
    VariableRollbackRequest,
)
from execution import python_executor, sql_executor, variables

router = APIRouter(tags=["execution"])


@router.post("/code")
def execute_code(request: CodeExecutionRequest) -> Dict[str, Any]:
    return python_executor.execute(request)


@router.post("/sql")
def execute_sql(request: SQLExecutionRequest) -> Dict[str, Any]:
    return sql_executor.execute(request)


@router.post("/rollback")
def rollback_variable(request: VariableRollbackRequest) -> Dict[str, Any]:
    return variables.rollback(request)


@router.post("/var")
def get_variable(request: VariableRetrievalRequest) -> Dict[str, Any]:
    return variables.get_variable(request)
