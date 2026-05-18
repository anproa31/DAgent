"""Databao Context Engine — FastAPI microservice."""
import logging
import os

from fastapi import FastAPI

from routers.api import router

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Databao Context Engine",
    description="Heuristic semantic inference for datasource schemas",
    version="0.1.0",
)

app.include_router(router)


@app.get("/")
async def root():
    return {"service": "databao-context-engine", "status": "running"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8002")))