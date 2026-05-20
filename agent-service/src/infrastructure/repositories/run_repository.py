"""Persistence for individual analysis runs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from interfaces.dto.db import AgentRun


async def create_run(
    db: AsyncSession,
    run_id: str,
    session_id: str,
    query: str,
) -> AgentRun:
    row = AgentRun(
        run_id=run_id,
        session_id=session_id,
        query=query,
        done=False,
        error=None,
        current_agent="",
        sql_draft=None,
        sql_explanation=None,
        sql_approved=False,
        pending_approval=False,
        insights=None,
        report_content=None,
        agent_steps=None,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def get_run(db: AsyncSession, run_id: str) -> Optional[AgentRun]:
    result = await db.execute(select(AgentRun).where(AgentRun.run_id == run_id))
    return result.scalar_one_or_none()


async def get_session_runs(db: AsyncSession, session_id: str) -> List[AgentRun]:
    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.session_id == session_id)
        .order_by(AgentRun.created_at.asc())
    )
    return list(result.scalars().all())


async def update_run(db: AsyncSession, run_id: str, **updates: Any) -> None:
    row = await get_run(db, run_id)
    if not row:
        return
    for key, val in updates.items():
        if hasattr(row, key):
            setattr(row, key, val)
    await db.commit()


def run_row_to_report_payload(row: AgentRun) -> Dict[str, Any]:
    """Map a stored AgentRun row to RunReportResponse-compatible dict."""
    content = row.report_content if row.report_content is not None else []
    agent_steps = row.agent_steps if isinstance(row.agent_steps, list) else []
    if not isinstance(content, list):
        content = []

    return {
        "done": row.done,
        "error": row.error or None,
        "query": row.query,
        "current_agent": row.current_agent or "",
        "sql_draft": row.sql_draft,
        "sql_explanation": row.sql_explanation,
        "sql_approved": bool(row.sql_approved),
        "pending_approval": bool(row.pending_approval),
        "insights": row.insights,
        "content": content,
        "agent_steps": agent_steps,
    }
