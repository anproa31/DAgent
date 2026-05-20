"""Tests for final report assembly."""
from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agents.analysis.final_report import (  # noqa: E402
    _has_reportable_content,
    final_report_node,
)


class TestFinalReportContentGate(unittest.TestCase):
    def test_viz_vars_count_as_reportable(self) -> None:
        state = {"error": "python error: crash", "viz_var_names": ["fig1"]}
        self.assertTrue(_has_reportable_content(state))

    def test_error_only_state_is_not_reportable(self) -> None:
        state = {"error": "python error: crash"}
        self.assertFalse(_has_reportable_content(state))

    def test_builds_analytical_report_when_viz_present_despite_error(self) -> None:
        state = {
            "intent": "ANALYTICAL",
            "session_id": "s1",
            "error": "python error: earlier crash",
            "viz_var_names": ["fig1"],
            "insights": "",
            "agent_steps": [],
        }
        image_block = {"type": "image", "base64": "abc123"}

        with patch(
            "agents.analysis.final_report.get_variable_results",
            new=AsyncMock(return_value=[image_block]),
        ):
            result = asyncio.run(final_report_node(state))

        types = [block["type"] for block in result["report_content"]]
        self.assertIn("image", types)
        self.assertTrue(result["done"])


if __name__ == "__main__":
    unittest.main()
