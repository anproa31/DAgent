"""Tests for user code sanitization."""
from __future__ import annotations

import unittest

from security.code_sanitizer import sanitize_user_code


class TestCodeSanitizer(unittest.TestCase):
    def test_escapes_backslash_placeholder(self) -> None:
        self.assertEqual(sanitize_user_code("x %@ y"), "x \\ y")

    def test_strips_duckdb_conn_reassignment(self) -> None:
        code = "duckdb_conn = None\nprint(1)"
        self.assertEqual(sanitize_user_code(code), "print(1)")

    def test_strips_engine_alias_reassignment(self) -> None:
        code = "engine = object()\n1 + 1"
        self.assertEqual(sanitize_user_code(code), "1 + 1")


if __name__ == "__main__":
    unittest.main()
