"""SQLAlchemy ORM models for persisted agent sessions and runs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    runs: Mapped[List["AgentRun"]] = relationship(
        "AgentRun",
        back_populates="session",
        order_by="AgentRun.created_at",
        cascade="all, delete-orphan",
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"

    run_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("agent_sessions.id", ondelete="CASCADE"), index=True
    )
    query: Mapped[str] = mapped_column(Text)
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_agent: Mapped[str] = mapped_column(String(128), default="")
    sql_draft: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sql_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sql_approved: Mapped[bool] = mapped_column(Boolean, default=False)
    pending_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    insights: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report_content: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    agent_steps: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    session: Mapped["AgentSession"] = relationship("AgentSession", back_populates="runs")
