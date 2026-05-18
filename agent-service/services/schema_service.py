import os
import httpx
from typing import Dict, Optional

APP_SERVICE_URL = os.getenv("APP_SERVICE_URL", "http://data-analysis-agent-app:8000")


async def get_schema(tables: Optional[list] = None) -> str:
    """Fetch schema markdown from app/ internal endpoint."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            params = {}
            if tables:
                params["tables"] = ",".join(tables)
            response = await client.get(
                f"{APP_SERVICE_URL}/internal/schema",
                params=params,
            )
            response.raise_for_status()
            data = response.json()
            schema_parts = data.get("schema", {})
            if isinstance(schema_parts, dict):
                # Filter to requested tables if specified
                if tables:
                    filtered = {k: v for k, v in schema_parts.items() if k in tables}
                    return "\n\n".join(filtered.values()) if filtered else "\n\n".join(schema_parts.values())
                return "\n\n".join(schema_parts.values())
            return str(schema_parts)
    except Exception as e:
        print(f"[schema_service] Failed to fetch schema: {e}")
        return "Schema unavailable"
