from pydantic import BaseModel
from typing import List, Optional


class CreateSessionRequest(BaseModel):
    title: str = ""


class StartRunRequest(BaseModel):
    query: str
    tables: List[str] = []
    model: str = ""
    base_url: str = ""
    api_key: str = ""


class ApproveRequest(BaseModel):
    sql: Optional[str] = None  # optionally edited SQL
    selected_urls: Optional[List[str]] = None
    name: Optional[str] = None


class RejectRequest(BaseModel):
    reason: str = "User rejected the generated SQL"
    sql: Optional[str] = None  # edited SQL that should be used for regeneration
    selected_urls: Optional[List[str]] = None
