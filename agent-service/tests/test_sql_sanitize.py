"""Tests for SQL markdown fence stripping."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from utils.sql_sanitize import clean_sql_for_execution  # noqa: E402


class TestCleanSqlForExecution(unittest.TestCase):
    def test_strips_sql_fenced_block(self) -> None:
        raw = """```sql

WITH filtered AS (
  SELECT 1
)
SELECT * FROM filtered;
```"""
        cleaned = clean_sql_for_execution(raw)
        assert cleaned.startswith("WITH filtered")
        assert "```" not in cleaned

    def test_strips_sql_label_and_fence(self) -> None:
        raw = "SQL: ```sql\nSELECT 1\n```\nEXPLANATION: counts rows"
        cleaned = clean_sql_for_execution(raw)
        assert cleaned == "SELECT 1"

    def test_plain_sql_unchanged(self) -> None:
        raw = "SELECT MaritalStatus FROM hr_employee_data LIMIT 5"
        assert clean_sql_for_execution(raw) == raw


if __name__ == "__main__":
    unittest.main()
