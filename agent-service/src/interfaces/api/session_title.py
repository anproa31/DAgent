"""Session title generation (decoupled from routers to avoid import cycles)."""

from __future__ import annotations

from infrastructure.database.connection import async_session_maker
from infrastructure.repositories import session_repository
from utils.llm_client import get_async_client, chat_complete


async def generate_title_from_query(
    query: str,
    model: str,
    base_url: str = "",
    api_key: str = "",
) -> str:
    try:
        client = get_async_client(base_url=base_url, api_key=api_key)
        messages = [
            {
                "role": "system",
                "content": """You are a title generator for data analysis sessions.
Generate a concise, descriptive title (max 60 characters) from this user query.
Do not include quotes or special characters. Just return the title text.""",
            },
            {"role": "user", "content": query},
        ]
        title = await chat_complete(client, model or "gpt-4o-mini", messages, temperature=0.2)
        return title.strip()[:60]
    except Exception:
        return query[:60] + "..." if len(query) > 60 else query


async def update_session_title_if_empty(
    session_id: str,
    query: str,
    model: str,
    base_url: str = "",
    api_key: str = "",
) -> str | None:
    title = await generate_title_from_query(query, model, base_url, api_key)
    async with async_session_maker() as db:
        sess = await session_repository.get_session(db, session_id)
        if not sess or not title or (sess.title or "").strip():
            return None
        await session_repository.set_session_title_if_empty(db, session_id, title)
        return title
