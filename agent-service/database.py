"""Async SQLAlchemy engine and session factory for the agent service."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

load_dotenv()

from models.db import Base

_DEFAULT_DB_PATH = Path(__file__).resolve().parent / "data" / "agent.db"

_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{_DEFAULT_DB_PATH}")

# Ensure SQLite directory exists when using default path
if _DATABASE_URL.startswith("sqlite+aiosqlite:///"):
    raw = _DATABASE_URL.replace("sqlite+aiosqlite:///", "", 1)
    if not raw.startswith(":memory:"):
        Path(raw).parent.mkdir(parents=True, exist_ok=True)

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
