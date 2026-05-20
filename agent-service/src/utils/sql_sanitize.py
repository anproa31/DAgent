"""Normalize SQL from LLM / UI before sandbox execution."""
from __future__ import annotations

import re

_EXPLANATION_SUFFIX = re.compile(r"\n\s*EXPLANATION:\s.*", re.DOTALL | re.IGNORECASE)
_SQL_PREFIX = re.compile(r"^SQL:\s*", re.IGNORECASE)
_FENCED_BLOCK = re.compile(
    r"```(?:sql)?\s*\n?(.*?)```",
    re.DOTALL | re.IGNORECASE,
)


def extract_sql_from_llm_response(raw: str) -> str:
    """Pull SQL text out of a SQL-agent LLM response before fence cleaning."""
    sql_match = re.search(r"SQL:\s*(.+?)(?=EXPLANATION:|$)", raw, re.DOTALL | re.IGNORECASE)
    if sql_match:
        return sql_match.group(1)
    fenced = _FENCED_BLOCK.search(raw)
    if fenced:
        return fenced.group(1)
    sel_match = re.search(r"(SELECT\b.+)", raw, re.DOTALL | re.IGNORECASE)
    return sel_match.group(1) if sel_match else raw


def clean_sql_for_execution(sql: str) -> str:
    """Remove markdown fences, ``SQL:`` labels, and trailing ``EXPLANATION:`` from SQL text."""
    if not sql:
        return ""
    text = sql.strip()
    text = _SQL_PREFIX.sub("", text).strip()

    fenced = _FENCED_BLOCK.search(text)
    if fenced:
        text = fenced.group(1).strip()
    else:
        text = re.sub(r"^```(?:sql)?\s*\n?", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\n?```\s*$", "", text)

    text = _EXPLANATION_SUFFIX.sub("", text).strip()
    return text
