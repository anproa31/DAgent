from fastapi import APIRouter
from pydantic import BaseModel

from utils.llm_client import get_async_client, chat_complete
from database import async_session_maker
from repositories import session_repository

router = APIRouter()


class GenerateTitleRequest(BaseModel):
    query: str
    model: str = ""
    base_url: str = ""
    api_key: str = ""


async def _generate_title_from_query(
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
Do not include quotes or special characters. Just return the title text."""
            },
            {"role": "user", "content": query}
        ]
        title = await chat_complete(client, model or "gpt-4o-mini", messages, temperature=0.2)
        title = title.strip()[:60]
        return title
    except Exception:
        fallback = query[:60] + "..." if len(query) > 60 else query
        return fallback


@router.post("/generate-title")
async def generate_title(body: GenerateTitleRequest) -> dict:
    title = await _generate_title_from_query(
        body.query, body.model, body.base_url, body.api_key
    )
    return {"title": title}


async def update_session_title_if_empty(
    session_id: str,
    query: str,
    model: str,
    base_url: str = "",
    api_key: str = "",
) -> str | None:
    """Generate an LLM title and persist it if the session has no title yet."""
    title = await _generate_title_from_query(query, model, base_url, api_key)
    async with async_session_maker() as db:
        sess = await session_repository.get_session(db, session_id)
        if not sess or not title or (sess.title or "").strip():
            return None
        await session_repository.set_session_title_if_empty(db, session_id, title)
        return title
