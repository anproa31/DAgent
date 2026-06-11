"""Async SQLAlchemy engine and session factory."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.settings import DATABASE_URL
from interfaces.dto.db import Base

load_dotenv()

_DATABASE_URL = os.getenv("DATABASE_URL", DATABASE_URL)

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
