import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import (
    analysis_router,
    datasources_router,
    health_router,
    internal_router,
    models_router,
    v1_router,
)
from .core.exceptions import register_exception_handlers
from .core.lifespan import lifespan

logging.basicConfig(level=logging.INFO)

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(datasources_router)
app.include_router(health_router)
app.include_router(analysis_router)
app.include_router(models_router)
app.include_router(internal_router)
app.include_router(v1_router)
