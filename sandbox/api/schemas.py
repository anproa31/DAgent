"""Request/response models for sandbox HTTP endpoints."""
from __future__ import annotations

from typing import Any, Dict, List

from pydantic import BaseModel


class RegisterDatasourceRequest(BaseModel):
    datasource_id: str
    name: str
    kind: str
    type: str
    view_names: List[str]
    config: Dict[str, Any] = {}
    sql_snippets: List[str] = []


class UnregisterDatasourceRequest(BaseModel):
    datasource_id: str
    view_names: List[str] = []


class CodeExecutionRequest(BaseModel):
    id: str
    code: str


class SQLExecutionRequest(BaseModel):
    id: str
    sql: str
    result_variable: str = "df_result"
    preview_limit: int = 20


class VariableRollbackRequest(BaseModel):
    id: str


class VariableRetrievalRequest(BaseModel):
    id: str
    name: str
