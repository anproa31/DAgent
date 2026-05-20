"""add streaming artifacts (thinking_segments, executions) to agent_runs

Revision ID: 002_streaming_artifacts
Revises: 001_initial
Create Date: 2026-05-21

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "002_streaming_artifacts"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_runs", sa.Column("thinking_segments", sa.JSON(), nullable=True))
    op.add_column("agent_runs", sa.Column("executions", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_runs", "executions")
    op.drop_column("agent_runs", "thinking_segments")
