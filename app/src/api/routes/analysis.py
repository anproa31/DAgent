from fastapi import APIRouter, Depends, HTTPException

from ...application.services.analysis_service import AnalysisService
from ...application.services.space_service import SpaceService
from ...infrastructure.external.llm_client import LLMClient
from ...models.requests import GenerateTitleRequest, StartAnalysisRequest
from ...models.responses import (
    CreateSpaceResponse,
    DeleteSpaceResponse,
    GenerateTitleResponse,
    GetReportResponse,
    GetSpaceResponse,
    StartAnalysisResponse,
    StopAnalysisResponse,
)
from ..dependencies.services import (
    get_analysis_service_dep,
    get_llm_client_dep,
    get_space_service,
)

router = APIRouter(tags=["analysis"])


@router.post("/start-analysis", response_model=StartAnalysisResponse)
async def start_analysis_endpoint(
    request: StartAnalysisRequest,
    analysis: AnalysisService = Depends(get_analysis_service_dep),
):
    try:
        analysis_id = analysis.start_analysis(request)
        return StartAnalysisResponse(id=analysis_id)
    except ValueError as e:
        return StartAnalysisResponse(error=str(e))
    except Exception as e:
        return StartAnalysisResponse(error=f"Analysis start error: {str(e)}")


@router.get("/get-report", response_model=GetReportResponse)
async def get_report(
    id: str,
    analysis: AnalysisService = Depends(get_analysis_service_dep),
):
    try:
        state = analysis.get_analysis_state(id)
        return GetReportResponse(
            done=state.get("done", True),
            progress=state.get("progress", ""),
            query=state.get("query", ""),
            error=state.get("error", ""),
            python_code=state.get("python_code", ""),
            steps=state.get("steps", []),
            content=state.get("content", []),
        )
    except Exception as e:
        return GetReportResponse(
            done=True,
            error=f"Report retrieval error: {str(e)}",
            progress="",
            query="",
            python_code="",
            content=[],
            steps=[],
        )


@router.post("/stop-analysis", response_model=StopAnalysisResponse)
async def stop_analysis_endpoint(
    id: str,
    analysis: AnalysisService = Depends(get_analysis_service_dep),
):
    try:
        found = analysis.stop_analysis(id)
        if not found:
            return StopAnalysisResponse(success=False, error="Analysis ID not found")
        return StopAnalysisResponse(success=True)
    except Exception as e:
        return StopAnalysisResponse(success=False, error=f"Stop error: {str(e)}")


@router.post("/create-space", response_model=CreateSpaceResponse)
async def create_space_endpoint(spaces: SpaceService = Depends(get_space_service)):
    try:
        space_id = spaces.create_space()
        return CreateSpaceResponse(id=space_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Space creation error: {str(e)}")


@router.get("/get-space/{space_id}", response_model=GetSpaceResponse)
async def get_space_endpoint(
    space_id: str, spaces: SpaceService = Depends(get_space_service)
):
    try:
        analysis_ids = spaces.get_space(space_id)
        return GetSpaceResponse(analysis_ids=analysis_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Space retrieval error: {str(e)}")


@router.delete("/delete-space/{space_id}", response_model=DeleteSpaceResponse)
async def delete_space_endpoint(
    space_id: str, spaces: SpaceService = Depends(get_space_service)
):
    try:
        deleted = spaces.delete_space(space_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Space not found")
        return DeleteSpaceResponse(success=True)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Space deletion error: {str(e)}")


@router.post("/generate-title", response_model=GenerateTitleResponse)
async def generate_title_endpoint(
    request: GenerateTitleRequest,
    llm: LLMClient = Depends(get_llm_client_dep),
):
    fallback = request.query[:50] + ("..." if len(request.query) > 50 else "")
    try:
        client = llm.get_openai_client(request.model) if request.model else None
        if client is None and llm.models:
            client = llm.get_openai_client(llm.models[0]["id"])
        if client is None:
            return GenerateTitleResponse(title=fallback)

        model_id = request.model if request.model else (
            llm.models[0]["id"] if llm.models else ""
        )
        if not model_id:
            return GenerateTitleResponse(title=fallback)

        response = await client.chat.completions.create(
            model=model_id,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate concise, descriptive chat titles. "
                        "Given a data analysis request, reply with ONLY a short title "
                        "(4-8 words, no quotes, no punctuation at the end). "
                        "The title should capture the main intent of the analysis."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Generate a title for this analysis request:\n{request.query}",
                },
            ],
            temperature=0.3,
            max_tokens=30,
        )
        raw = (response.choices[0].message.content or "").strip().strip('"').strip("'")
        return GenerateTitleResponse(title=raw if raw else fallback)
    except Exception:
        return GenerateTitleResponse(title=fallback)
