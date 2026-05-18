"""Persistence for chat / analysis sessions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.db import AgentSession


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def create_session(db: AsyncSession, session_id: str, title: str = "") -> AgentSession:
    now = _utcnow()
    row = AgentSession(
        id=session_id,
        title=title or "",
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def ensure_session(
    db: AsyncSession, session_id: str, title: str = ""
) -> AgentSession:
    """Create the session row if missing (e.g. legacy clients)."""
    existing = await get_session(db, session_id)
    if existing:
        return existing
    return await create_session(db, session_id, title=title)


async def get_session(db: AsyncSession, session_id: str) -> Optional[AgentSession]:
    result = await db.execute(
        select(AgentSession).where(
            AgentSession.id == session_id,
            AgentSession.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def get_session_with_runs(db: AsyncSession, session_id: str) -> Optional[AgentSession]:
    result = await db.execute(
        select(AgentSession)
        .options(selectinload(AgentSession.runs))
        .where(
            AgentSession.id == session_id,
            AgentSession.deleted_at.is_(None),
        )
    )
    return result.scalar_one_or_none()


async def list_sessions(db: AsyncSession) -> Sequence[AgentSession]:
    result = await db.execute(
        select(AgentSession)
        .where(AgentSession.deleted_at.is_(None))
        .order_by(AgentSession.updated_at.desc())
    )
    return result.scalars().all()


async def delete_session(db: AsyncSession, session_id: str) -> bool:
    res = await db.execute(
        update(AgentSession)
        .where(
            AgentSession.id == session_id,
            AgentSession.deleted_at.is_(None),
        )
        .values(deleted_at=_utcnow(), updated_at=_utcnow())
    )
    await db.commit()
    return res.rowcount > 0


async def touch_session(db: AsyncSession, session_id: str) -> None:
    await db.execute(
        update(AgentSession)
        .where(AgentSession.id == session_id)
        .values(updated_at=_utcnow())
    )
    await db.commit()


async def set_session_title_if_empty(
    db: AsyncSession, session_id: str, title: str
) -> None:
    sess = await get_session(db, session_id)
    if not sess or not title:
        return
    if (sess.title or "").strip():
        return
    await db.execute(
        update(AgentSession)
        .where(AgentSession.id == session_id)
        .values(title=title[:512], updated_at=_utcnow())
    )
    await db.commit()
