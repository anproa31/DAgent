"""Integration tests for the layered sandbox runtime."""
from __future__ import annotations

import asyncio
import unittest

import pandas as pd

from control_layer import TaskObject, get_control_layer
from execution.response import to_http_response
from execution.serialization import to_json, to_response_payload
from infrastructure.duckdb import startup as duckdb_startup
from infrastructure.duckdb import shutdown as duckdb_shutdown
from security.code_sanitizer import sanitize_user_code, validate_user_code


class TestControlLayer(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        asyncio.run(duckdb_startup())

    @classmethod
    def tearDownClass(cls) -> None:
        asyncio.run(duckdb_shutdown())

    def setUp(self) -> None:
        self.control = get_control_layer()
        self.session_id = "test-session-layered"

    def tearDown(self) -> None:
        self.control.handle_task(
            TaskObject(task_type="disconnect", session_id=self.session_id)
        )

    def test_execute_code_and_get_variable(self) -> None:
        code_result = self.control.handle_task(
            TaskObject(
                task_type="execute_code",
                session_id=self.session_id,
                code="x = 42",
            )
        )
        self.assertEqual(code_result.status.value, "success")

        var_result = self.control.handle_task(
            TaskObject(
                task_type="get_variable",
                session_id=self.session_id,
                variable_name="x",
            )
        )
        payload = to_http_response(var_result)
        self.assertIn("result", payload)
        self.assertEqual(payload["result"][0]["data"], "42")

    def test_execute_sql_materializes_dataframe(self) -> None:
        sql_result = self.control.handle_task(
            TaskObject(
                task_type="execute_sql",
                session_id=self.session_id,
                sql="SELECT 1 AS a, 2 AS b",
                result_variable="df_result",
            )
        )
        payload = to_http_response(sql_result)
        self.assertTrue(payload.get("ok"))
        self.assertEqual(payload["rows"], 1)


class TestSerialization(unittest.TestCase):
    def test_dataframe_serializes_as_table(self) -> None:
        payload = to_json(pd.DataFrame({"a": [1, 2]}))
        self.assertEqual(payload["type"], "table")
        self.assertIn("data", payload)

    def test_scalar_wraps_in_list(self) -> None:
        result = to_response_payload(42)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["type"], "string")
        self.assertEqual(result[0]["data"], "42")


class TestCodeSanitizer(unittest.TestCase):
    def test_escapes_backslash_placeholder(self) -> None:
        self.assertEqual(sanitize_user_code("x %@ y"), "x \\ y")

    def test_strips_duckdb_conn_reassignment(self) -> None:
        code = "duckdb_conn = None\nprint(1)"
        self.assertEqual(sanitize_user_code(code), "print(1)")

    def test_validate_user_code_returns_warnings(self) -> None:
        warnings = validate_user_code("import subprocess")
        self.assertTrue(any("subprocess" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
