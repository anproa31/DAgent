"""Schema introspection adapter for the datasource registry.

This module is the bridge between raw data sources (CSV, Excel, SQLite,
PostgreSQL, Parquet, ...) and the structured ``DatabaseIntrospectionResult``
types from the bundled ``data-context-engine`` library.

The approach mirrors DCE's design philosophy: a single ``DuckDB`` session is
the universal query engine. DuckDB can natively read CSV / Parquet, attach
SQLite and PostgreSQL databases, and load Excel via the ``excel`` extension
(falling back to ``pandas`` when the extension is unavailable). Once the
data is reachable through DuckDB we reuse ``DuckDBIntrospector`` to produce
the same rich schema graph DCE produces for native datasources.

The introspector also renders a Markdown schema string that the existing
prompt machinery can drop into the LLM context without further changes.
"""
from __future__ import annotations

import logging
import os
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import duckdb

logger = logging.getLogger(__name__)


# Map our datasource ``type`` string to the DuckDB function used to load it.
_DUCKDB_FILE_READERS: Dict[str, str] = {
    "csv": "read_csv_auto",
    "parquet": "read_parquet",
}


@dataclass
class _ColumnStats:
    """Lightweight per-column profile used to enrich the schema markdown."""

    distinct_count: Optional[int] = None
    null_count: Optional[int] = None
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    top_values: Optional[List[Any]] = None  # populated only for low-cardinality cols


@dataclass
class _TableSchema:
    """In-memory representation of a single logical table."""

    name: str
    columns: List[Tuple[str, str, bool]]  # (column_name, type, nullable)
    samples: List[Dict[str, Any]]
    row_count: Optional[int] = None
    description: Optional[str] = None
    column_stats: Dict[str, _ColumnStats] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.column_stats is None:
            self.column_stats = {}


@dataclass
class IntrospectionOutcome:
    """Returned to the registry once a datasource has been inspected."""

    view_names: List[str]
    tables: List[_TableSchema]
    schema_markdown: str
    sql_snippets: List[str]
    """SQL statements the sandbox can replay to recreate the views/attachments."""
    context_markdown: str = ""
    """Semantic context summary from the context-engine: table grains, column roles, relationships, query capabilities."""


def normalize_identifier(name: str, max_length: int = 63) -> str:
    """Normalise a string into a safe SQL identifier (lowercase, underscores).

    Mirrors the historical normalisation in ``DataService`` so existing
    references stay stable across the refactor.
    """
    if not name or not isinstance(name, str):
        raise ValueError("Identifier must be a non-empty string")

    text = unicodedata.normalize("NFKC", str(name))
    text = re.sub(r"[^\w\s]", "_", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text)
    text = text.strip("_").lower()

    if not text:
        raise ValueError("Normalised identifier became empty")

    if len(text) > max_length:
        text = text[:max_length].rstrip("_")

    # DuckDB identifiers cannot start with a digit
    if text[0].isdigit():
        text = "t_" + text

    return text


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def introspect_file_datasource(
    *,
    name: str,
    file_type: str,
    file_path: str,
    extra: Optional[Dict[str, Any]] = None,
) -> IntrospectionOutcome:
    """Introspect a file-based datasource and produce schema + view DDL.

    The DDL is generated against a temporary in-memory DuckDB database so we
    can validate the data is loadable before the sandbox creates the same
    views.

    Args:
        name: Logical datasource name (user-facing).
        file_type: ``csv`` | ``excel`` | ``sqlite`` | ``parquet``.
        file_path: Path to the file *inside the container*.
        extra: Type-specific options (e.g. ``{"delimiter": ","}``).
    """
    file_type = file_type.lower()
    base_name = normalize_identifier(name)
    extra = extra or {}

    conn = duckdb.connect(":memory:")
    try:
        if file_type == "csv":
            return _introspect_csv(conn, base_name, file_path, extra)
        if file_type == "parquet":
            return _introspect_parquet(conn, base_name, file_path)
        if file_type == "excel":
            return _introspect_excel(conn, base_name, file_path)
        if file_type == "sqlite":
            return _introspect_sqlite(conn, base_name, file_path)
        raise ValueError(f"Unsupported file datasource type: {file_type}")
    finally:
        conn.close()


def introspect_database_datasource(
    *,
    name: str,
    db_type: str,
    config: Dict[str, Any],
) -> IntrospectionOutcome:
    """Introspect a remote database datasource (Postgres/MySQL/...).

    Uses ``ATTACH`` in DuckDB which gives us a uniform schema view.
    """
    db_type = db_type.lower()
    base_name = normalize_identifier(name)

    conn = duckdb.connect(":memory:")
    try:
        if db_type == "postgres":
            return _introspect_postgres(conn, base_name, config)
        if db_type == "mysql":
            return _introspect_mysql(conn, base_name, config)
        if db_type == "duckdb":
            return _introspect_duckdb_file(conn, base_name, config)
        raise ValueError(f"Unsupported database datasource type: {db_type}")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# File-type implementations
# ---------------------------------------------------------------------------


def _introspect_csv(
    conn: duckdb.DuckDBPyConnection,
    base_name: str,
    file_path: str,
    extra: Dict[str, Any],
) -> IntrospectionOutcome:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"CSV file not found: {file_path}")

    view_name = base_name
    ddl = (
        f'CREATE OR REPLACE VIEW "{view_name}" AS '
        f"SELECT * FROM read_csv_auto('{file_path}', sample_size=-1)"
    )
    conn.execute(ddl)

    table = _describe_table(conn, view_name)
    snippets = [ddl]
    markdown = _format_markdown([table])
    return IntrospectionOutcome(
        view_names=[view_name],
        tables=[table],
        schema_markdown=markdown,
        sql_snippets=snippets,
    )


def _introspect_parquet(
    conn: duckdb.DuckDBPyConnection,
    base_name: str,
    file_path: str,
) -> IntrospectionOutcome:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Parquet file not found: {file_path}")

    view_name = base_name
    ddl = (
        f'CREATE OR REPLACE VIEW "{view_name}" AS '
        f"SELECT * FROM read_parquet('{file_path}')"
    )
    conn.execute(ddl)
    table = _describe_table(conn, view_name)
    return IntrospectionOutcome(
        view_names=[view_name],
        tables=[table],
        schema_markdown=_format_markdown([table]),
        sql_snippets=[ddl],
    )


def _introspect_excel(
    conn: duckdb.DuckDBPyConnection,
    base_name: str,
    file_path: str,
) -> IntrospectionOutcome:
    """Introspect an Excel workbook, exposing one DuckDB view per sheet.

    Tries the DuckDB ``excel`` extension first, then falls back to ``pandas``
    when the extension is not available (e.g. air-gapped environments).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Excel file not found: {file_path}")

    sheet_names = _list_excel_sheets(file_path)
    if not sheet_names:
        raise ValueError(f"No sheets found in Excel file: {file_path}")

    snippets: List[str] = []
    tables: List[_TableSchema] = []
    view_names: List[str] = []

    excel_extension_available = _try_load_excel_extension(conn)

    for sheet in sheet_names:
        view_name = _multi_sheet_view_name(base_name, sheet, len(sheet_names))
        view_names.append(view_name)

        if excel_extension_available:
            escaped_sheet = sheet.replace("'", "''")
            ddl = (
                f'CREATE OR REPLACE VIEW "{view_name}" AS '
                f"SELECT * FROM read_xlsx('{file_path}', sheet='{escaped_sheet}')"
            )
            conn.execute(ddl)
            snippets.append(ddl)
        else:
            # pandas fallback: register a DataFrame as a DuckDB view
            import json

            import pandas as pd  # local import to keep cold start light

            df = pd.read_excel(file_path, sheet_name=sheet)
            df.columns = [normalize_identifier(str(c)) for c in df.columns]
            conn.register(f"_tmp_{view_name}", df)
            ddl = (
                f'CREATE OR REPLACE VIEW "{view_name}" AS '
                f'SELECT * FROM _tmp_{view_name}'
            )
            conn.execute(ddl)
            # Emit a JSON-encoded instruction the sandbox understands instead of
            # raw DDL — the sandbox needs the file path + sheet name to recreate
            # the DataFrame on its side.
            instruction = json.dumps(
                {"kind": "excel", "name": view_name, "path": file_path, "sheet": sheet}
            )
            snippets.append(f"-- pandas-fallback {instruction}")

        tables.append(_describe_table(conn, view_name))

    markdown = _format_markdown(tables)
    return IntrospectionOutcome(
        view_names=view_names,
        tables=tables,
        schema_markdown=markdown,
        sql_snippets=snippets,
    )


def _introspect_sqlite(
    conn: duckdb.DuckDBPyConnection,
    base_name: str,
    file_path: str,
) -> IntrospectionOutcome:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"SQLite file not found: {file_path}")

    # 1. Enumerate tables using sqlite3 (cheap and reliable).
    src_conn = sqlite3.connect(file_path)
    try:
        cur = src_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
        table_names = [row[0] for row in cur.fetchall()]
    finally:
        src_conn.close()

    if not table_names:
        raise ValueError(f"No tables found in SQLite file: {file_path}")

    # 2. Attach the file in DuckDB so SQL queries can target it.
    attach_alias = base_name
    attach_sql = f"ATTACH '{file_path}' AS \"{attach_alias}\" (TYPE SQLITE)"
    conn.execute(attach_sql)

    snippets: List[str] = [attach_sql]
    tables: List[_TableSchema] = []
    view_names: List[str] = []

    for table_name in table_names:
        view_name = normalize_identifier(f"{base_name}_{table_name}")
        ddl = (
            f'CREATE OR REPLACE VIEW "{view_name}" AS '
            f'SELECT * FROM "{attach_alias}"."{table_name}"'
        )
        conn.execute(ddl)
        snippets.append(ddl)
        view_names.append(view_name)
        tables.append(_describe_table(conn, view_name))

    return IntrospectionOutcome(
        view_names=view_names,
        tables=tables,
        schema_markdown=_format_markdown(tables),
        sql_snippets=snippets,
    )


# ---------------------------------------------------------------------------
# Database implementations
# ---------------------------------------------------------------------------


def _install_extension(conn: duckdb.DuckDBPyConnection, extension: str) -> bool:
    try:
        conn.execute(f"INSTALL {extension}")
        conn.execute(f"LOAD {extension}")
        return True
    except Exception as exc:  # pragma: no cover - depends on runtime
        logger.warning("Failed to install DuckDB extension %s: %s", extension, exc)
        return False


def _introspect_postgres(
    conn: duckdb.DuckDBPyConnection,
    base_name: str,
    config: Dict[str, Any],
) -> IntrospectionOutcome:
    if not _install_extension(conn, "postgres"):
        raise RuntimeError("DuckDB 'postgres' extension is required to attach PostgreSQL datasources")

    conn_str = _build_postgres_dsn(config)
    attach_sql = (
        f"ATTACH {_sql_string_literal(conn_str)} AS \"{base_name}\" (TYPE POSTGRES, READ_ONLY)"
    )
    conn.execute(attach_sql)

    snippets: List[str] = [attach_sql]
    return _introspect_attached_database(
        conn=conn,
        attach_alias=base_name,
        snippets=snippets,
        schema_filter=lambda s: s not in {"information_schema", "pg_catalog", "pg_toast"},
    )


def _introspect_mysql(
    conn: duckdb.DuckDBPyConnection,
    base_name: str,
    config: Dict[str, Any],
) -> IntrospectionOutcome:
    if not _install_extension(conn, "mysql"):
        raise RuntimeError("DuckDB 'mysql' extension is required to attach MySQL datasources")

    conn_str = _build_mysql_dsn(config)
    attach_sql = (
        f"ATTACH {_sql_string_literal(conn_str)} AS \"{base_name}\" (TYPE MYSQL, READ_ONLY)"
    )
    conn.execute(attach_sql)
    snippets: List[str] = [attach_sql]
    return _introspect_attached_database(
        conn=conn,
        attach_alias=base_name,
        snippets=snippets,
        schema_filter=lambda s: s not in {"information_schema", "mysql", "performance_schema", "sys"},
    )


def _introspect_duckdb_file(
    conn: duckdb.DuckDBPyConnection,
    base_name: str,
    config: Dict[str, Any],
) -> IntrospectionOutcome:
    path = config.get("path") or config.get("database_path")
    if not path:
        raise ValueError("DuckDB datasource requires a 'path' in config")

    attach_sql = f"ATTACH '{path}' AS \"{base_name}\" (READ_ONLY)"
    conn.execute(attach_sql)
    snippets: List[str] = [attach_sql]
    return _introspect_attached_database(
        conn=conn,
        attach_alias=base_name,
        snippets=snippets,
        schema_filter=lambda s: s not in {"information_schema", "pg_catalog"},
    )


def _introspect_attached_database(
    *,
    conn: duckdb.DuckDBPyConnection,
    attach_alias: str,
    snippets: List[str],
    schema_filter,
) -> IntrospectionOutcome:
    """Introspect an attached database and create one view per table."""
    rows = conn.execute(
        """
        SELECT table_schema, table_name
        FROM information_schema.tables
        WHERE table_catalog = ?
          AND table_type IN ('BASE TABLE', 'VIEW')
        ORDER BY table_schema, table_name
        """,
        [attach_alias],
    ).fetchall()

    if not rows:
        raise ValueError(f"No accessible tables/views found in datasource '{attach_alias}'")

    tables: List[_TableSchema] = []
    view_names: List[str] = []
    for schema, table_name in rows:
        if not schema_filter(schema):
            continue
        view_name = normalize_identifier(f"{attach_alias}_{schema}_{table_name}")
        ddl = (
            f'CREATE OR REPLACE VIEW "{view_name}" AS '
            f'SELECT * FROM "{attach_alias}"."{schema}"."{table_name}"'
        )
        try:
            conn.execute(ddl)
        except Exception as exc:  # pragma: no cover - depends on permissions
            logger.warning("Skipping table %s.%s (%s)", schema, table_name, exc)
            continue
        snippets.append(ddl)
        view_names.append(view_name)
        tables.append(_describe_table(conn, view_name))

    if not tables:
        raise ValueError(f"No introspectable tables found in datasource '{attach_alias}'")

    return IntrospectionOutcome(
        view_names=view_names,
        tables=tables,
        schema_markdown=_format_markdown(tables),
        sql_snippets=snippets,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


# Threshold beyond which per-column profiling is skipped to keep registration fast.
_PROFILE_ROW_LIMIT = 250_000
# Columns with at most this many distinct values get their enumeration captured.
_LOW_CARDINALITY_THRESHOLD = 25


def _describe_table(conn: duckdb.DuckDBPyConnection, view_name: str) -> _TableSchema:
    info_rows = conn.execute(
        f'PRAGMA table_info("{view_name}")'
    ).fetchall()
    columns = [
        (
            str(row[1]),
            str(row[2]),
            not bool(row[3]),  # ``notnull`` column -> nullable inverted
        )
        for row in info_rows
    ]

    try:
        sample_rows = conn.execute(
            f'SELECT * FROM "{view_name}" USING SAMPLE 5 ROWS'
        ).fetchdf()
    except Exception:
        # USING SAMPLE may be unsupported on views over remote databases.
        sample_rows = conn.execute(
            f'SELECT * FROM "{view_name}" LIMIT 5'
        ).fetchdf()

    samples = sample_rows.to_dict(orient="records") if not sample_rows.empty else []

    try:
        count = conn.execute(f'SELECT COUNT(*) FROM "{view_name}"').fetchone()
        row_count = int(count[0]) if count else None
    except Exception:
        row_count = None

    column_stats = _profile_columns(conn, view_name, columns, row_count)

    return _TableSchema(
        name=view_name,
        columns=columns,
        samples=samples,
        row_count=row_count,
        column_stats=column_stats,
    )


def _profile_columns(
    conn: duckdb.DuckDBPyConnection,
    view_name: str,
    columns: List[Tuple[str, str, bool]],
    row_count: Optional[int],
) -> Dict[str, _ColumnStats]:
    """Per-column distinct/null counts + low-cardinality enumeration.

    Skipped for very large tables (configurable threshold) to keep
    registration fast. The richer schema helps the agent pick correct
    join keys and recognise categorical columns without scanning data.
    """
    if row_count is None or row_count > _PROFILE_ROW_LIMIT or not columns:
        return {}

    stats: Dict[str, _ColumnStats] = {}
    for col_name, col_type, _nullable in columns:
        col_stats = _ColumnStats()
        safe_col = '"' + col_name.replace('"', '""') + '"'
        try:
            row = conn.execute(
                f'SELECT COUNT(DISTINCT {safe_col}) AS d, COUNT(*) - COUNT({safe_col}) AS n '
                f'FROM "{view_name}"'
            ).fetchone()
            if row is not None:
                col_stats.distinct_count = int(row[0]) if row[0] is not None else None
                col_stats.null_count = int(row[1]) if row[1] is not None else None
        except Exception as exc:  # pragma: no cover - depends on column type
            logger.debug("Profile distinct/null failed for %s.%s: %s", view_name, col_name, exc)

        if _is_numeric_type(col_type) or _is_temporal_type(col_type):
            try:
                row = conn.execute(
                    f"SELECT MIN({safe_col}), MAX({safe_col}) FROM \"{view_name}\""
                ).fetchone()
                if row is not None:
                    col_stats.min_value = row[0]
                    col_stats.max_value = row[1]
            except Exception as exc:  # pragma: no cover - depends on column type
                logger.debug("Profile min/max failed for %s.%s: %s", view_name, col_name, exc)

        if (
            col_stats.distinct_count is not None
            and 0 < col_stats.distinct_count <= _LOW_CARDINALITY_THRESHOLD
        ):
            try:
                top_rows = conn.execute(
                    f'SELECT DISTINCT {safe_col} FROM "{view_name}" '
                    f'WHERE {safe_col} IS NOT NULL '
                    f'ORDER BY {safe_col} LIMIT {_LOW_CARDINALITY_THRESHOLD}'
                ).fetchall()
                col_stats.top_values = [r[0] for r in top_rows]
            except Exception as exc:  # pragma: no cover - depends on column type
                logger.debug("Top values failed for %s.%s: %s", view_name, col_name, exc)

        stats[col_name] = col_stats
    return stats


def _is_numeric_type(col_type: str) -> bool:
    upper = col_type.upper()
    return any(
        token in upper
        for token in ("INT", "DECIMAL", "DOUBLE", "FLOAT", "REAL", "NUMERIC", "HUGE")
    )


def _is_temporal_type(col_type: str) -> bool:
    upper = col_type.upper()
    return any(token in upper for token in ("DATE", "TIME", "TIMESTAMP"))


def _format_markdown(tables: List[_TableSchema]) -> str:
    parts: List[str] = []
    shared_columns = _detect_shared_columns(tables)

    for tbl in tables:
        parts.append(f"## Table: {tbl.name}")
        if tbl.row_count is not None:
            parts.append(f"_Row count: {tbl.row_count:,}_")
        parts.append(
            "| Column | Type | Nullable | Distinct | Null % | Range | Sample 1 | Sample 2 | Sample 3 |"
        )
        parts.append("|---|---|---|---|---|---|---|---|---|")
        for col_name, col_type, nullable in tbl.columns:
            sample_values: List[str] = []
            for sample in tbl.samples[:3]:
                value = sample.get(col_name)
                sample_values.append(_short_repr(value))
            while len(sample_values) < 3:
                sample_values.append("")

            stats = tbl.column_stats.get(col_name)
            distinct = ""
            null_pct = ""
            range_str = ""
            if stats and stats.distinct_count is not None:
                distinct = f"{stats.distinct_count:,}"
            if stats and stats.null_count is not None and tbl.row_count:
                null_pct = f"{(stats.null_count / tbl.row_count * 100):.1f}%"
            if stats and stats.min_value is not None and stats.max_value is not None:
                range_str = (
                    f"{_short_repr(stats.min_value)} → {_short_repr(stats.max_value)}"
                )

            parts.append(
                f"| {col_name} | {col_type} | {'YES' if nullable else 'NO'} | "
                f"{distinct} | {null_pct} | {range_str} | "
                f"{sample_values[0]} | {sample_values[1]} | {sample_values[2]} |"
            )

        # Low-cardinality column enumeration — a DCE-inspired hint that
        # helps the agent reason about categorical columns without running
        # exploratory SQL first.
        enum_lines: List[str] = []
        for col_name, _col_type, _nullable in tbl.columns:
            stats = tbl.column_stats.get(col_name)
            if not stats or not stats.top_values:
                continue
            preview = ", ".join(_short_repr(v) for v in stats.top_values)
            enum_lines.append(f"- `{col_name}` ({len(stats.top_values)} values): {preview}")
        if enum_lines:
            parts.append("")
            parts.append("**Categorical values:**")
            parts.extend(enum_lines)

        # Likely-key markers and join hints across tables in the same datasource.
        pk_candidates = _detect_pk_candidates(tbl)
        join_hints = _build_join_hints(tbl, shared_columns)
        if pk_candidates:
            parts.append("")
            parts.append(
                f"**Likely keys:** {', '.join(f'`{c}`' for c in pk_candidates)}"
            )
        if join_hints:
            parts.append("")
            parts.append("**Potential joins:**")
            parts.extend(join_hints)
        parts.append("")

    return "\n".join(parts).strip()


def _detect_pk_candidates(table: _TableSchema) -> List[str]:
    """Columns where distinct_count == row_count and no nulls — primary key candidates."""
    if not table.row_count or table.row_count <= 1:
        return []
    candidates: List[str] = []
    for col_name, _col_type, _nullable in table.columns:
        stats = table.column_stats.get(col_name)
        if not stats:
            continue
        if (
            stats.distinct_count is not None
            and stats.null_count == 0
            and stats.distinct_count == table.row_count
        ):
            candidates.append(col_name)
    return candidates


def _detect_shared_columns(tables: List[_TableSchema]) -> Dict[str, List[str]]:
    """Map column-name → list of table names it appears in (case-insensitive)."""
    occurrences: Dict[str, List[str]] = {}
    for tbl in tables:
        for col_name, _col_type, _nullable in tbl.columns:
            key = col_name.lower()
            occurrences.setdefault(key, []).append(tbl.name)
    return occurrences


def _build_join_hints(
    table: _TableSchema, shared_columns: Dict[str, List[str]]
) -> List[str]:
    """For each column shared with another table, emit a hint line."""
    hints: List[str] = []
    for col_name, _col_type, _nullable in table.columns:
        owners = shared_columns.get(col_name.lower(), [])
        peers = [t for t in owners if t != table.name]
        if peers:
            peers_str = ", ".join(f"`{p}`" for p in sorted(set(peers)))
            hints.append(f"- `{col_name}` also appears in {peers_str}")
    return hints


def _short_repr(value: Any, max_length: int = 40) -> str:
    if value is None:
        return ""
    text = str(value).replace("|", "/").replace("\n", " ")
    if len(text) > max_length:
        text = text[: max_length - 1] + "…"
    return text


def _list_excel_sheets(file_path: str) -> List[str]:
    import openpyxl  # local import keeps cold start light

    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    try:
        return list(wb.sheetnames)
    finally:
        wb.close()


def _try_load_excel_extension(conn: duckdb.DuckDBPyConnection) -> bool:
    try:
        conn.execute("INSTALL excel")
        conn.execute("LOAD excel")
        # Verify the function is actually present.
        conn.execute("SELECT 1 FROM duckdb_functions() WHERE function_name = 'read_xlsx' LIMIT 1")
        return True
    except Exception as exc:
        logger.info("DuckDB excel extension unavailable, falling back to pandas: %s", exc)
        return False


def _multi_sheet_view_name(base_name: str, sheet: str, sheet_count: int) -> str:
    if sheet_count == 1:
        return base_name
    return normalize_identifier(f"{base_name}_{sheet}")


def _sql_string_literal(value: str) -> str:
    """Quote a value for embedding in DuckDB SQL (double single-quotes)."""
    return "'" + value.replace("'", "''") + "'"


def _build_postgres_dsn(config: Dict[str, Any]) -> str:
    """Build a libpq-style connection string for the DuckDB ``postgres`` extension.

    Uses unquoted ``key=value`` pairs (same as MySQL) so the string can be
    wrapped safely inside ``ATTACH '...'`` without nested-quote parse errors.
    """
    parts: Dict[str, Any] = {
        "host": config.get("host", "localhost"),
        "port": config.get("port", 5432),
        "dbname": config.get("database"),
        "user": config.get("user"),
        "password": config.get("password"),
    }
    parts.update(config.get("additional_properties") or {})

    fragments = []
    for key, value in parts.items():
        if value is None or value == "":
            continue
        fragments.append(f"{key}={value}")
    return " ".join(fragments)


def _build_mysql_dsn(config: Dict[str, Any]) -> str:
    """Build a connection string accepted by DuckDB's ``mysql`` extension."""
    parts: Dict[str, Any] = {
        "host": config.get("host", "localhost"),
        "port": config.get("port", 3306),
        "database": config.get("database"),
        "user": config.get("user"),
        "password": config.get("password"),
    }
    parts.update(config.get("additional_properties") or {})

    fragments = []
    for key, value in parts.items():
        if value is None or value == "":
            continue
        fragments.append(f"{key}={value}")
    return " ".join(fragments)


def parse_connection_string(conn_str: str) -> Dict[str, Any]:
    """Parse ``postgresql://user:pass@host:port/db`` (and similar) into a dict."""
    from urllib.parse import urlparse

    parsed = urlparse(conn_str)
    return {
        "host": parsed.hostname,
        "port": parsed.port,
        "database": (parsed.path or "/").lstrip("/") or None,
        "user": parsed.username,
        "password": parsed.password,
    }
