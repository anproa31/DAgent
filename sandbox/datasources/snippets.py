"""Apply SQL/DDL snippets and pandas-fallback instructions to DuckDB."""
from __future__ import annotations

import json

import pandas as pd

from api.schemas import RegisterDatasourceRequest
from infrastructure.duckdb import get_connection
from infrastructure.logging_setup import logger

PANDAS_FALLBACK_PREFIX = "-- pandas-fallback "


def apply_snippet(snippet: str, request: RegisterDatasourceRequest) -> None:
    snippet = snippet.strip()
    if not snippet:
        return
    if snippet.startswith(PANDAS_FALLBACK_PREFIX):
        apply_pandas_fallback(snippet[len(PANDAS_FALLBACK_PREFIX) :], request)
        return
    if snippet.startswith("--"):
        return
    get_connection().execute(snippet)


def apply_pandas_fallback(payload: str, request: RegisterDatasourceRequest) -> None:
    """Realise a sheet/file as a DuckDB view via pandas."""
    try:
        instruction = json.loads(payload)
    except json.JSONDecodeError as exc:
        logger.warning("Malformed pandas-fallback payload %r: %s", payload, exc)
        return

    kind = instruction.get("kind")
    name = instruction.get("name")
    path = instruction.get("path")
    sheet = instruction.get("sheet")

    if kind != "excel" or not name or not path:
        logger.warning("Unsupported pandas-fallback instruction: %s", instruction)
        return

    df = pd.read_excel(path, sheet_name=sheet) if sheet else pd.read_excel(path)
    df.columns = [str(c) for c in df.columns]
    conn = get_connection()
    conn.register(f"_tmp_{name}", df)
    conn.execute(f'CREATE OR REPLACE VIEW "{name}" AS SELECT * FROM _tmp_{name}')
