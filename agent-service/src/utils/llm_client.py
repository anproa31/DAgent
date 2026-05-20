import os
import openai
from typing import Optional

from utils.agent_logger import get_logger, truncate

logger = get_logger("llm")


def get_async_client(base_url: str = "", api_key: str = "") -> openai.AsyncOpenAI:
    """Build an AsyncOpenAI client with the given or env-configured settings."""
    resolved_base = base_url or os.getenv("OPENAI_BASE_URL", "")
    resolved_key = api_key or os.getenv("OPENAI_API_KEY", "none")

    # Normalise URL (same logic as app/)
    resolved_base = resolved_base.replace("http://localhost:", "http://host.docker.internal:")
    resolved_base = resolved_base.rstrip("/")
    if not resolved_base.endswith("/v1"):
        resolved_base = resolved_base.replace("/v1/", "").replace("/v1", "") + "/v1"

    if not resolved_key:
        resolved_key = "none"

    return openai.AsyncOpenAI(base_url=resolved_base, api_key=resolved_key)


async def chat_complete(
    client: openai.AsyncOpenAI,
    model: str,
    messages: list,
    temperature: float = 0.2,
    stream: bool = False,
    log_tag: str = "llm",
) -> str:
    """Helper: non-streaming chat completion, returns content string."""
    roles = [m.get("role", "?") for m in messages]
    last_user = next(
        (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
        "",
    )
    logger.info(
        "[%s] request model=%s temperature=%s messages=%d roles=%s",
        log_tag,
        model,
        temperature,
        len(messages),
        roles,
    )
    logger.debug("[%s] last user message: %s", log_tag, truncate(last_user, 800))

    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        stream=stream,
    )
    content = response.choices[0].message.content or ""
    logger.info(
        "[%s] response (%d chars): %s",
        log_tag,
        len(content),
        truncate(content, int(os.getenv("LOG_LLM_RESPONSE_MAX", "4000"))),
    )
    return content
