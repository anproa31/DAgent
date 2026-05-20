"""Backward-compatible LLM model utilities."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import openai

from .infrastructure.external.llm_client import LLMClient, get_llm_client, reset_llm_client

MODELS: List[Dict[str, Any]] = []
OPENAI_CLIENTS: Dict[str, openai.AsyncOpenAI] = {}


def _sync_cache_from_client(client: LLMClient) -> None:
    global MODELS, OPENAI_CLIENTS
    MODELS = client.models
    OPENAI_CLIENTS = client._openai_clients


async def get_model_list_async(base_url: str, api_key: str) -> List[Dict[str, Any]]:
    client = get_llm_client()
    models = await client.fetch_models(base_url, api_key)
    _sync_cache_from_client(client)
    return models


def get_model_list(base_url: str, api_key: str) -> List[Dict[str, Any]]:
    """Sync wrapper for route compatibility during migration."""
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, get_model_list_async(base_url, api_key))
            return future.result()
    return asyncio.run(get_model_list_async(base_url, api_key))


def get_openai_client(model_id: str) -> Optional[openai.AsyncOpenAI]:
    return get_llm_client().get_openai_client(model_id)


def get_model_by_id(model_id: str) -> Dict[str, Any]:
    return get_llm_client().get_model_by_id(model_id)


def string_to_uuid(text: str) -> str:
    import hashlib

    return hashlib.md5(text.encode()).hexdigest()
