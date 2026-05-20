"""Tests for variable response serialization."""
from __future__ import annotations

import unittest

import pandas as pd

from execution.serialization import to_json, to_response_payload


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


if __name__ == "__main__":
    unittest.main()
