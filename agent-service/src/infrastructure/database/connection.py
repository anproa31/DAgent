"""Async SQLAlchemy engine and session factory."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.settings import DATABASE_URL, DEFAULT_DB_PATH
from interfaces.dto.db import Base

load_dotenv()

_DATABASE_URL = os.getenv("DATABASE_URL", DATABASE_URL)

if _DATABASE_URL.startswith("sqlite+aiosqlite:///"):
    raw = _DATABASE_URL.replace("sqlite+aiosqlite:///", "", 1)
    if not raw.startswith(":memory:"):
        Path(raw).parent.mkdir(parents=True, exist_ok=True)
elif not Path(DEFAULT_DB_PATH).parent.exists():
    Path(DEFAULT_DB_PATH).parent.mkdir(parents=True, exist_ok=True)

engine = create_async_engine(
    _DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "").lower() in ("1", "true", "yes"),
)

async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


async def init_db() -> None:
    """Create tables if they do not exist (dev fallback; production should use Alembic)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
