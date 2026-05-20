"""Tests for web fetch URL validation."""
from __future__ import annotations

import unittest

from application.services.web_security import (
    domain_trust_score,
    looks_like_data_file,
    validate_fetch_url,
)


class TestWebSecurity(unittest.TestCase):
    def test_trusted_gov_domain(self) -> None:
        result = validate_fetch_url(
            "https://data.cms.gov/sites/default/files/2024-01/sample.csv"
        )
        self.assertTrue(result.ok)
        self.assertGreater(result.trust_score, 0)

    def test_blocks_http(self) -> None:
        result = validate_fetch_url("http://example.com/data.csv")
        self.assertFalse(result.ok)

    def test_blocks_localhost(self) -> None:
        result = validate_fetch_url("https://localhost/data.csv")
        self.assertFalse(result.ok)

    def test_data_file_on_github_raw(self) -> None:
        url = "https://raw.githubusercontent.com/org/repo/main/data.csv"
        self.assertTrue(looks_like_data_file(url))
        result = validate_fetch_url(url)
        self.assertTrue(result.ok)

    def test_untrusted_blog_rejected_by_default(self) -> None:
        result = validate_fetch_url("https://random-blog.example/file.csv")
        self.assertFalse(result.ok)

    def test_untrusted_allowed_when_flag_set(self) -> None:
        result = validate_fetch_url(
            "https://random-blog.example/file.csv",
            allow_untrusted=True,
        )
        self.assertTrue(result.ok)

    def test_worldbank_trust_score(self) -> None:
        score = domain_trust_score("data.worldbank.org")
        self.assertGreaterEqual(score, 60)


if __name__ == "__main__":
    unittest.main()
