"""LLM model discovery and OpenAI client cache."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
import openai

from ...core.config import Settings, get_settings


class LLMClient:
    """Fetches model lists and caches AsyncOpenAI clients per model id."""

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self._settings = settings
        self.models: List[Dict[str, Any]] = []
        self._openai_clients: Dict[str, openai.AsyncOpenAI] = {}

    async def fetch_models(self, base_url: str, api_key: str) -> List[Dict[str, Any]]:
        normalized_url = self._normalize_base_url(base_url)
        model_names = await self._fetch_model_names(normalized_url, api_key)
        self.models = []
        self._openai_clients = {}
        for model_name in model_names:
            model_id = model_name
            self.models.append(
                {
                    "id": model_id,
                    "model_name": model_name,
                    "base_url": normalized_url,
                    "api_key": api_key,
                    "display_name": model_name,
                    "description": "",
                    "config": {},
                }
            )
            key = api_key if api_key else "none"
            self._openai_clients[model_id] = openai.AsyncOpenAI(
                base_url=normalized_url, api_key=key
            )
        return self.models

    def get_openai_client(self, model_id: str) -> Optional[openai.AsyncOpenAI]:
        return self._openai_clients.get(model_id)

    def get_model_by_id(self, model_id: str) -> Dict[str, Any]:
        for model in self.models:
            if model["id"] == model_id:
                return model
        raise ValueError(f"Model ID {model_id} not found.")

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        base_url = base_url.replace("http://localhost:", "http://host.docker.internal:")
        base_url = base_url.replace("/v1/", "")
        base_url = base_url.replace("/v1", "")
        return base_url + "/v1"

    @staticmethod
    async def _fetch_model_names(base_url: str, api_key: str) -> List[str]:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    f"{base_url}/models",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
            if response.status_code == 200:
                models = response.json().get("data", [])
                if models:
                    return [m["id"] for m in models]
            return ["no models available"]
        except httpx.HTTPError:
            return ["no models available"]


_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client


def reset_llm_client() -> None:
    global _llm_client
    _llm_client = None
