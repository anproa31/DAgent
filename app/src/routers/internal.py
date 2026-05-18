from fastapi import APIRouter, Query
from typing import Optional
from ..database import engine
from ..db_to_schema import main as db_to_schema_main

router = APIRouter(prefix="/internal")


@router.get("/schema")
async def get_schema(tables: Optional[str] = Query(None)):
    """
    Return the database schema in markdown format.
    Used by agent-service to build LLM context without duplicating DB config.
    `tables` is an optional comma-separated list of table names to filter.
    """
    schema_dict = db_to_schema_main(engine)
    if "error" in schema_dict:
        return {"schema": {}, "error": schema_dict["error"]}

    if tables:
        requested = [t.strip() for t in tables.split(",") if t.strip()]
        schema_dict = {k: v for k, v in schema_dict.items() if k in requested}

    return {"schema": schema_dict}
