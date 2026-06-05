import sys
from contextlib import asynccontextmanager
from pathlib import Path

# Ensure `src/` is on the import path (local dev and Docker without PYTHONPATH).
_SRC = Path(__file__).resolve().parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from infrastructure.database.connection import init_db
from interfaces.api.routers import (
    kb_router,
    runs_router,
    sessions_router,
    skills_router,
    title_router,
)
from utils.agent_logger import get_logger, setup_logging

setup_logging()
logger = get_logger("agent-service")

# DCE must use host Ollama in Docker; patch before any context search.
from context.dce_integration import patch_dce_ollama

patch_dce_ollama()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Agent service starting")
    await init_db()
    yield
    logger.info("Agent service shutting down")


app = FastAPI(title="Data Analytics Agent Service", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions_router, prefix="/agent")
app.include_router(runs_router, prefix="/agent")
app.include_router(title_router, prefix="/agent")
app.include_router(kb_router, prefix="/agent")
app.include_router(skills_router, prefix="/agent")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "agent-service"}
