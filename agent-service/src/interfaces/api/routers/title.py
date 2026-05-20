from fastapi import APIRouter
from pydantic import BaseModel

from interfaces.api.session_title import generate_title_from_query

router = APIRouter()


class GenerateTitleRequest(BaseModel):
    query: str
    model: str = ""
    base_url: str = ""
    api_key: str = ""


@router.post("/generate-title")
async def generate_title(body: GenerateTitleRequest) -> dict:
    title = await generate_title_from_query(
        body.query, body.model, body.base_url, body.api_key
    )
    return {"title": title}
