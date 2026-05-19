from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import sessions_router, runs_router, title_router

from database import init_db
from utils.agent_logger import get_logger, setup_logging

setup_logging()
logger = get_logger("agent-service")


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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "agent-service"}
