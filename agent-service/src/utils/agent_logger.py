"""Shared logging helpers for agent flow and LLM debugging."""
from __future__ import annotations

import logging
import os
from typing import Any

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_LLM_RESPONSE_MAX = int(os.getenv("LOG_LLM_RESPONSE_MAX", "4000"))
LOG_TEXT_MAX = int(os.getenv("LOG_TEXT_MAX", "500"))

_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    _configured = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)


def truncate(text: Any, max_len: int | None = None) -> str:
    """Truncate long strings for readable log lines."""
    if text is None:
        return ""
    s = text if isinstance(text, str) else str(text)
    limit = max_len if max_len is not None else LOG_TEXT_MAX
    if len(s) <= limit:
        return s
    return f"{s[:limit]}… ({len(s)} chars total)"


def log_llm_response(logger: logging.Logger, tag: str, raw: str) -> None:
    """Log a model response with a configurable max length."""
    logger.info("[%s] model response (%d chars): %s", tag, len(raw), truncate(raw, LOG_LLM_RESPONSE_MAX))
