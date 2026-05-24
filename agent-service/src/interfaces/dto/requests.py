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
    # Memory selection (composer @ / pickers) + embedding override (Settings UI).
    kb_documents: List[str] = []
    skill_ids: List[str] = []
    embedding_base_url: str = ""
    embedding_model: str = ""


class SkillCreate(BaseModel):
    name: str
    description: str
    template: str
    skill_type: str = "sql"  # "sql" | "chart" | "pipeline"


class SkillUpdate(BaseModel):
    name: str
    description: str
    template: str


class ApproveRequest(BaseModel):
    sql: Optional[str] = None  # optionally edited SQL
    code: Optional[str] = None  # optionally edited Python (python_review)
    selected_urls: Optional[List[str]] = None
    name: Optional[str] = None


class RejectRequest(BaseModel):
    reason: str = "User rejected the generated SQL"
    sql: Optional[str] = None  # edited SQL that should be used for regeneration
    code: Optional[str] = None  # edited Python (python_review)
    selected_urls: Optional[List[str]] = None
