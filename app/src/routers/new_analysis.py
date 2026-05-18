from fastapi import APIRouter, HTTPException
from ..models.requests import StartAnalysisRequest, GenerateTitleRequest
from ..models.responses import StartAnalysisResponse, GetReportResponse, CreateSpaceResponse, GetSpaceResponse, DeleteSpaceResponse, StopAnalysisResponse, GenerateTitleResponse
from ..analysis_manager import start_analysis, get_analysis_state, create_space, get_space, delete_space, stop_analysis
from ..utils.llm_models import get_openai_client, MODELS

router = APIRouter()

@router.post("/start-analysis", response_model=StartAnalysisResponse)
async def start_analysis_endpoint(request: StartAnalysisRequest):
    """Start an analysis"""
    try:
        analysis_id = start_analysis(request)
        return StartAnalysisResponse(id=analysis_id)
    except ValueError as e:
        # Validation error
        return StartAnalysisResponse(error=str(e))
    except Exception as e:
        return StartAnalysisResponse(error=f"Analysis start error: {str(e)}")

@router.get("/get-report", response_model=GetReportResponse)
async def get_report(id: str):
    """Retrieve analysis results"""
    try:
        state = get_analysis_state(id)

        return GetReportResponse(
            done=state.get("done", True),
            progress=state.get("progress", ""),
            query=state.get("query", ""),
            error=state.get("error", ""),
            python_code=state.get("python_code", ""),
            steps=state.get("steps", []),
            content=state.get("content", [])
        )
    except Exception as e:
        return GetReportResponse(
            done=True,
            error=f"Report retrieval error: {str(e)}",
            progress="",
            query="",
            python_code="",
            content=[],
            steps=[]
        )

@router.post("/stop-analysis", response_model=StopAnalysisResponse)
async def stop_analysis_endpoint(id: str):
    """Stop a running analysis"""
    try:
        found = stop_analysis(id)
        if not found:
            return StopAnalysisResponse(success=False, error="Analysis ID not found")
        return StopAnalysisResponse(success=True)
    except Exception as e:
        return StopAnalysisResponse(success=False, error=f"Stop error: {str(e)}")

# Create and retrieve spaces
@router.post("/create-space", response_model=CreateSpaceResponse)
async def create_space_endpoint():
    """Create a new space"""
    try:
        space_id = create_space()
        return CreateSpaceResponse(id=space_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Space creation error: {str(e)}")

@router.get("/get-space/{space_id}", response_model=GetSpaceResponse)
async def get_space_endpoint(space_id: str):
    """Retrieve the analysis IDs for the specified space ID"""
    try:
        analysis_ids = get_space(space_id)
        return GetSpaceResponse(analysis_ids=analysis_ids)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Space retrieval error: {str(e)}")

@router.delete("/delete-space/{space_id}", response_model=DeleteSpaceResponse)
async def delete_space_endpoint(space_id: str):
    """Delete a space and all its associated analyses"""
    try:
        deleted = delete_space(space_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Space not found")
        return DeleteSpaceResponse(success=True)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Space deletion error: {str(e)}")

@router.post("/generate-title", response_model=GenerateTitleResponse)
async def generate_title_endpoint(request: GenerateTitleRequest):
    """Use the LLM to generate a short, descriptive title for a chat session based on the user query."""
    fallback = request.query[:50] + ("..." if len(request.query) > 50 else "")
    try:
        client = get_openai_client(request.model) if request.model else None
        if client is None and MODELS:
            client = get_openai_client(MODELS[0]["id"])
        if client is None:
            return GenerateTitleResponse(title=fallback)

        model_id = request.model if request.model else (MODELS[0]["id"] if MODELS else "")
        if not model_id:
            return GenerateTitleResponse(title=fallback)

        response = await client.chat.completions.create(
            model=model_id,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You generate concise, descriptive chat titles. "
                        "Given a data analysis request, reply with ONLY a short title (4-8 words, no quotes, no punctuation at the end). "
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
        title = raw if raw else fallback
        return GenerateTitleResponse(title=title)
    except Exception:
        return GenerateTitleResponse(title=fallback)