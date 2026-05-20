"""Tests for the sandbox tool registry and executor."""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tools.executor import run_tool  # noqa: E402
from tools.registry import format_tools_for_prompt, get_tool, list_tools  # noqa: E402


class TestToolRegistry(unittest.TestCase):
    def test_list_tools_includes_core_sandbox_tools(self) -> None:
        names = {tool.name for tool in list_tools()}
        self.assertIn("execute_python", names)
        self.assertIn("execute_sql", names)
        self.assertIn("get_variable", names)
        self.assertIn("discover_web_data", names)
        self.assertIn("fetch_web_data", names)

    def test_format_tools_for_prompt_renders_schema(self) -> None:
        prompt = format_tools_for_prompt()
        self.assertIn("execute_sql", prompt)
        self.assertIn("execute_python", prompt)

    def test_unknown_tool_returns_error(self) -> None:
        result = asyncio.run(run_tool("session-1", "missing_tool"))
        self.assertFalse(result.success)
        self.assertIn("Unknown tool", result.error or "")


class TestToolExecutor(unittest.TestCase):
    def test_execute_sql_success(self) -> None:
        mock_result = {
            "ok": True,
            "rows": 2,
            "columns": ["a", "b"],
            "preview": [{"a": 1, "b": 2}],
            "result_variable": "df_result",
        }
        with patch(
            "tools.handlers.execute_sql",
            new=AsyncMock(return_value=mock_result),
        ):
            result = asyncio.run(
                run_tool("session-1", "execute_sql", sql="SELECT 1 AS a, 2 AS b")
            )

        self.assertTrue(result.success)
        self.assertEqual(result.data["rows"], 2)
        self.assertTrue(any(chunk["output_type"] == "table" for chunk in result.chunks))

    def test_execute_python_failure(self) -> None:
        with patch(
            "tools.handlers.execute_code",
            new=AsyncMock(return_value={"code_error": "SyntaxError"}),
        ):
            result = asyncio.run(
                run_tool("session-1", "execute_python", code="bad syntax {{{")
            )

        self.assertFalse(result.success)
        self.assertEqual(result.error, "SyntaxError")
        self.assertTrue(get_tool("execute_python") is not None)

    def test_get_variable_accepts_name_kwarg(self) -> None:
        """Regression: tool dispatch param must be ``tool_name``, not ``name``."""
        mock_var = {
            "result": [{"type": "table", "data": {"columns": ["a"], "rows": [[1]]}}]
        }
        with patch(
            "tools.handlers.get_variable",
            new=AsyncMock(return_value=mock_var),
        ):
            result = asyncio.run(
                run_tool("session-1", "get_variable", name="df_result")
            )

        self.assertTrue(result.success)
        self.assertEqual(result.data.get("variable_name"), "df_result")


if __name__ == "__main__":
    unittest.main()
