"""Sandbox service entry point.

Dual-mode Python + SQL executor backed by DuckDB. See package modules under
``api/``, ``execution/``, ``datasources/``, ``infrastructure/``, and ``security/``.
"""
from __future__ import annotations

from app_factory import create_app

app = create_app()
