"""Pydantic models for the context engine API."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ColumnInfo(BaseModel):
    name: str
    type: str
    nullable: bool = True


class ColumnStats(BaseModel):
    distinct_count: Optional[int] = None
    null_count: Optional[int] = None
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    top_values: Optional[List[Any]] = None


class TableInfo(BaseModel):
    name: str
    columns: List[ColumnInfo]
    row_count: Optional[int] = None
    samples: List[Dict[str, Any]] = []
    column_stats: Dict[str, ColumnStats] = {}


class BuildRequest(BaseModel):
    datasource_name: str
    tables: List[TableInfo]


class BuildResponse(BaseModel):
    context_summary: str
    domain: str
    table_grains: Dict[str, str]
    query_capabilities: List[str]


class EnhanceRequest(BaseModel):
    context_summary: str
    query: str
    datasources: Optional[List[Dict[str, Any]]] = None


class EnhanceResponse(BaseModel):
    enhanced_context: str


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
