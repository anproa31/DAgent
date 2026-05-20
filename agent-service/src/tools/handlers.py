"""Sandbox tool handlers — thin wrappers over the HTTP execution client."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from infrastructure.sandbox.code_runner import (
    execute_code,
    execute_sql,
    get_variable,
    get_variable_results,
    rollback_session,
)
from tools.chunks import code_chunk, content_blocks_from_variable_result, table_chunk, text_chunk
from tools.schemas import ToolResult
from utils.sql_sanitize import clean_sql_for_execution


def _build_sql_summary(columns: List[str], row_count: int, preview: List[Dict[str, Any]]) -> str:
    if not columns:
        return "No data returned"
    if row_count == 0:
        return f"Columns: {columns}\nRow count: 0"
    header = " | ".join(columns)
    preview_lines = [
        " | ".join(str(row.get(col, "")) for col in columns) for row in preview[:5]
    ]
    return (
        f"Columns: {columns}\n"
        f"Row count: {row_count}\n"
        f"Preview ({min(5, row_count)} rows):\n"
        f"{header}\n" + "\n".join(preview_lines)
    )


def _build_variable_summary(var_result: Optional[Dict[str, Any]]) -> str:
    if not var_result or "result" not in var_result:
        return "No data returned"
    try:
        for item in var_result["result"]:
            if item.get("type") == "table":
                rows = json.loads(item["data"])
                if not rows:
                    return "Empty table result"
                columns = list(rows[0].keys())
                row_count = len(rows)
                header = " | ".join(columns)
                preview_lines = [
                    " | ".join(str(row.get(col, "")) for col in columns) for row in rows[:5]
                ]
                return (
                    f"Columns: {columns}\n"
                    f"Row count: {row_count}\n"
                    f"Preview ({min(5, row_count)} rows):\n"
                    f"{header}\n" + "\n".join(preview_lines)
                )
        return "Result available but no table data"
    except Exception as exc:
        return f"Data summary unavailable: {exc}"


async def handle_execute_python(session_id: str, code: str) -> ToolResult:
    if not code or not code.strip():
        return ToolResult(
            success=False,
            chunks=[text_chunk("No Python code provided")],
            error="No Python code provided",
        )

    result = await execute_code(code, session_id)
    if "code_error" in result or "error" in result:
        err = result.get("code_error") or result.get("error")
        return ToolResult(
            success=False,
            chunks=[code_chunk(code.strip()), text_chunk(f"Execution error: {err}")],
            data={"python_code": code.strip()},
            error=str(err),
        )

    return ToolResult(
        success=True,
        chunks=[code_chunk(code.strip()), text_chunk("Python code executed successfully")],
        data={"python_code": code.strip()},
    )


async def handle_execute_sql(
    session_id: str,
    sql: str,
    result_variable: str = "df_result",
) -> ToolResult:
    sql = clean_sql_for_execution(sql)
    if not sql:
        return ToolResult(
            success=False,
            chunks=[text_chunk("No SQL provided")],
            error="No SQL provided",
        )

    result = await execute_sql(sql, session_id, result_variable=result_variable)
    if "code_error" in result or "error" in result:
        err = result.get("code_error") or result.get("error")
        return ToolResult(
            success=False,
            chunks=[code_chunk(sql), text_chunk(f"SQL execution failed: {err}")],
            data={"sql": sql, "result_variable": result_variable},
            error=str(err),
        )

    columns: List[str] = result.get("columns", [])
    rows = int(result.get("rows", 0))
    preview: List[Dict[str, Any]] = result.get("preview", [])
    data_summary = _build_sql_summary(columns, rows, preview)

    chunks = [
        code_chunk(sql),
        text_chunk(data_summary),
    ]
    if preview:
        chunks.append(table_chunk(preview))

    return ToolResult(
        success=True,
        chunks=chunks,
        data={
            "sql": sql,
            "result_variable": result.get("result_variable", result_variable),
            "columns": columns,
            "rows": rows,
            "preview": preview,
            "data_summary": data_summary,
            "result_var_names": [result_variable],
        },
    )


async def handle_get_variable(session_id: str, name: str) -> ToolResult:
    if not name:
        return ToolResult(
            success=False,
            chunks=[text_chunk("Variable name is required")],
            error="Variable name is required",
        )

    var_result = await get_variable(session_id, name)
    if not var_result:
        return ToolResult(
            success=False,
            chunks=[text_chunk(f"Variable '{name}' not found")],
            data={"variable_name": name},
            error=f"Variable '{name}' not found",
        )

    blocks = content_blocks_from_variable_result(var_result)
    chunks = [text_chunk(f"Variable '{name}' retrieved")]
    for block in blocks:
        if block.get("type") == "table":
            chunks.append(table_chunk(block.get("table")))
        elif block.get("type") == "image":
            from tools.chunks import image_chunk

            chunks.append(image_chunk(block.get("base64", "")))
        else:
            chunks.append(text_chunk(str(block.get("data", ""))))

    return ToolResult(
        success=True,
        chunks=chunks,
        data={
            "variable_name": name,
            "variable_result": var_result,
            "content_blocks": blocks,
            "data_summary": _build_variable_summary(var_result),
        },
    )


async def handle_get_variables(session_id: str, names: List[str]) -> ToolResult:
    if not names:
        return ToolResult(
            success=False,
            chunks=[text_chunk("At least one variable name is required")],
            error="At least one variable name is required",
        )

    blocks = await get_variable_results(session_id, names)
    chunks = [text_chunk(f"Retrieved {len(names)} variable(s)")]
    for block in blocks:
        if block.get("type") == "table":
            chunks.append(table_chunk(block.get("table")))
        elif block.get("type") == "image":
            from tools.chunks import image_chunk

            chunks.append(image_chunk(block.get("base64", "")))

    return ToolResult(
        success=True,
        chunks=chunks,
        data={"variable_names": names, "content_blocks": blocks},
    )


async def handle_rollback(session_id: str) -> ToolResult:
    result = await rollback_session(session_id)
    if "error" in result:
        return ToolResult(
            success=False,
            chunks=[text_chunk(f"Rollback failed: {result['error']}")],
            error=str(result["error"]),
        )
    return ToolResult(
        success=True,
        chunks=[text_chunk("Session variables rolled back")],
    )
