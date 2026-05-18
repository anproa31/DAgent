from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import (
    data_router,
    health_router,
    internal_router,
    model_list_router,
    new_analysis_router,
)
from .utils.prompts import set_db_schema

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(data_router)
app.include_router(health_router)
app.include_router(new_analysis_router)
app.include_router(model_list_router)
app.include_router(internal_router)


@app.on_event("startup")
async def startup_event() -> None:
    """Warm the prompt cache from the datasource registry."""
    set_db_schema()
