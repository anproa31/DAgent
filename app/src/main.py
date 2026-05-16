from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from .routers import data_router, health_router, new_analysis_router,model_list_router
from .utils.prompts import set_db_schema

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Check this value as needed
    allow_credentials=True,
    allow_methods=["*"],  # Ensure OPTIONS method is allowed
    allow_headers=["*"],
)

# Register routers
app.include_router(data_router)
app.include_router(health_router)
app.include_router(new_analysis_router)
app.include_router(model_list_router)

# Set up the database schema on application startup
@app.on_event("startup")
async def startup_event():
    # Configure the database schema
    set_db_schema()