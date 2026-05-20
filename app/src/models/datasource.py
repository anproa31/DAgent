"""Pydantic models describing datasources tracked by the registry."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class DatasourceKind(str, Enum):
    """High-level category for a datasource."""

    FILE = "file"
    DATABASE = "database"


class DatasourceFileType(str, Enum):
    """Supported file-based datasource types."""

    CSV = "csv"
    EXCEL = "excel"
    SQLITE = "sqlite"
    PARQUET = "parquet"


class DatasourceDatabaseType(str, Enum):
    """Supported database connection datasource types."""

    POSTGRES = "postgres"
    MYSQL = "mysql"
    MSSQL = "mssql"
    DUCKDB = "duckdb"
    CLICKHOUSE = "clickhouse"


class DatasourceTableInfo(BaseModel):
    """Lightweight schema info for one logical table within a datasource."""

    name: str
    column_count: int = 0
    row_count: Optional[int] = None
    description: Optional[str] = None


class DatasourceRecord(BaseModel):
    """A single registered datasource.

    `view_names` is the list of DuckDB views or attached schema-qualified
    table names that the sandbox will create when this datasource is
    registered. They are how the SQL/Python agents reference the data.
    """

    id: str
    name: str
    kind: DatasourceKind
    type: str  # csv | excel | sqlite | parquet | postgres | mysql | ...
    config: Dict[str, Any] = Field(default_factory=dict)
    """Type-specific configuration.

    For files: ``{"path": "<absolute path inside container>", "original_filename": "..."}``.
    For databases: connection details (host, port, database, user, password, ...).
    """
    view_names: List[str] = Field(default_factory=list)
    """Names of DuckDB views/tables the sandbox should expose for this datasource."""
    tables: List[DatasourceTableInfo] = Field(default_factory=list)
    schema_markdown: str = ""
    """Pre-rendered markdown schema description, suitable for LLM prompts."""
    context_summary: str = ""
    """Semantic context summary from the context-engine: table grains, column roles, relationships, query capabilities."""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None


class CreateFileDatasourceResponse(BaseModel):
    datasources: List[DatasourceRecord]
    message: str = ""


class CreateDatabaseDatasourceRequest(BaseModel):
    name: str
    type: DatasourceDatabaseType
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    connection_string: Optional[str] = None
    """Optional fallback: a SQLAlchemy-style URL ``postgresql://user:pass@host:port/db``.

    When provided it is parsed to fill the structured fields above.
    """
    additional_properties: Dict[str, Any] = Field(default_factory=dict)


class DatasourceListResponse(BaseModel):
    datasources: List[DatasourceRecord]


class DeleteDatasourceResponse(BaseModel):
    success: bool
    deleted_id: str


class FetchUrlDatasourceRequest(BaseModel):
    url: str
    name: Optional[str] = None


class DiscoverWebDataRequest(BaseModel):
    query: str
    name: Optional[str] = None
    url: Optional[str] = None
    """Optional direct URL — skips search when provided."""
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    max_results: int = Field(default=3, ge=1, le=5)


class WebDiscoverCandidate(BaseModel):
    title: str
    url: str
    snippet: str = ""
    score: int = 0
    reason: str = ""


class DiscoverWebDataResponse(BaseModel):
    query: str
    search_count: int = 0
    candidates: List[WebDiscoverCandidate] = Field(default_factory=list)
    selected_urls: List[str] = Field(default_factory=list)
    datasources: List[DatasourceRecord] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    message: str = ""


class RegisterWebDataRequest(BaseModel):
    urls: List[str]
    name: Optional[str] = None
    query: Optional[str] = None
