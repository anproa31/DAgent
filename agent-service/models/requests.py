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


class RejectRequest(BaseModel):
    reason: str = "User rejected the generated SQL"
