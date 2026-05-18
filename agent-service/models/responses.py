from pydantic import BaseModel
from typing import List, Optional, Any


class CreateSessionResponse(BaseModel):
    session_id: str


class SessionRunSummary(BaseModel):
    run_id: str
    query: str
    done: bool
    error: Optional[str] = None


class SessionRunsResponse(BaseModel):
    session_id: str
    runs: List[SessionRunSummary] = []


class StartRunResponse(BaseModel):
    run_id: str
    error: Optional[str] = None


class ApproveResponse(BaseModel):
    success: bool
    error: Optional[str] = None


class RejectResponse(BaseModel):
    success: bool
    error: Optional[str] = None


class ReportContent(BaseModel):
    type: str  # markdown | image | table | variable
    content: Optional[str] = None
    base64: Optional[str] = None
    table: Optional[str] = None
    data: Optional[str] = None


class RunReportResponse(BaseModel):
    done: bool
    error: Optional[str] = None
    query: str = ""
    current_agent: str = ""
    sql_draft: Optional[str] = None
    sql_explanation: Optional[str] = None
    sql_approved: bool = False
    pending_approval: bool = False
    insights: Optional[str] = None
    content: List[Any] = []
    agent_steps: List[str] = []
