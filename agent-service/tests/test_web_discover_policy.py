"""Tests for web discovery gating policy."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agents.shared.web_discover_policy import needs_web_discover, should_use_discover_action  # noqa: E402


class TestWebDiscoverPolicy(unittest.TestCase):
    def test_no_datasources_requires_discover(self) -> None:
        allowed, reason = needs_web_discover({"datasources": [], "query": "GDP by country"})
        self.assertTrue(allowed)
        self.assertIn("No datasources", reason)

    def test_existing_datasource_blocks_by_default(self) -> None:
        state = {
            "datasources": [{"name": "sales", "view_names": ["sales"]}],
            "schema_info": "# Datasource: sales",
            "last_observation": {},
        }
        allowed, _ = needs_web_discover(state)
        self.assertFalse(allowed)

    def test_data_discovery_error_allows_discover(self) -> None:
        state = {
            "datasources": [{"name": "sales", "view_names": ["sales"]}],
            "schema_info": "schema",
            "last_observation": {
                "artifacts": {"data_discovery_error": "table not found: hr_employees"},
            },
        }
        allowed, reason = needs_web_discover(state)
        self.assertTrue(allowed)
        self.assertIn("table not found", reason)

    def test_should_use_discover_action_matches_needs(self) -> None:
        state = {"datasources": [], "query": "x"}
        self.assertEqual(should_use_discover_action(state), needs_web_discover(state))


if __name__ == "__main__":
    unittest.main()
