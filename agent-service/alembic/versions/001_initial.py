"""initial agent_sessions and agent_runs

Revision ID: 001_initial
Revises:
Create Date: 2026-05-18

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "agent_runs",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("done", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("current_agent", sa.String(length=128), nullable=False),
        sa.Column("sql_draft", sa.Text(), nullable=True),
        sa.Column("sql_explanation", sa.Text(), nullable=True),
        sa.Column("sql_approved", sa.Boolean(), nullable=False),
        sa.Column("pending_approval", sa.Boolean(), nullable=False),
        sa.Column("insights", sa.Text(), nullable=True),
        sa.Column("report_content", sa.JSON(), nullable=True),
        sa.Column("agent_steps", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["agent_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id"),
    )
    op.create_index("ix_agent_runs_session_id", "agent_runs", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_runs_session_id", table_name="agent_runs")
    op.drop_table("agent_runs")
    op.drop_table("agent_sessions")
