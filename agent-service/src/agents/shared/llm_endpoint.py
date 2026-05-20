"""Shared OpenAI-compatible endpoint helpers for agent-patterns adapters."""

from __future__ import annotations

import os


def normalize_base_url(base_url: str) -> str | None:
    resolved = (base_url or os.getenv("OPENAI_BASE_URL", "")).strip()
    resolved = resolved.replace("http://localhost:", "http://host.docker.internal:")
    resolved = resolved.rstrip("/")
    if resolved and not resolved.endswith("/v1"):
        resolved = resolved.replace("/v1/", "").replace("/v1", "") + "/v1"
    return resolved or None
