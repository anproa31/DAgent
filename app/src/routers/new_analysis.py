from fastapi import APIRouter, HTTPException
from ..models.requests import StartAnalysisRequest
from ..models.responses import StartAnalysisResponse, GetReportResponse, CreateSpaceResponse, GetSpaceResponse, DeleteSpaceResponse, StopAnalysisResponse
from ..analysis_manager import start_analysis, get_analysis_state, create_space, get_space, delete_space, stop_analysis

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