from fastapi import APIRouter, Depends

from ...infrastructure.external.llm_client import LLMClient
from ...models.responses import GetModelListResponse, LLMMODEL
from ..dependencies.services import get_llm_client_dep

router = APIRouter(tags=["models"])


@router.get("/get-model-list", response_model=GetModelListResponse)
async def get_model_list(
    base_url: str,
    api_key: str = "",
    llm: LLMClient = Depends(get_llm_client_dep),
):
    models = await llm.fetch_models(base_url, api_key)
    return GetModelListResponse(
        models=[
            LLMMODEL(
                id=model["id"],
                name=model["display_name"] or model["model_name"],
                description=model["description"],
            )
            for model in models
        ]
    )
