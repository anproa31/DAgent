"""Logging configuration for the sandbox worker."""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def configure_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(level=level)
