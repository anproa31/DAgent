import os
import openai
from typing import Awaitable, Callable, Optional

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
    on_delta: Optional[Callable[[str], Awaitable[None]]] = None,
) -> str:
    """Helper: chat completion, returns the full content string.

    When ``on_delta`` is provided the request is streamed and each token delta is
    forwarded to the callback (used to stream the model's reasoning/generation to
    the SSE ``thinking_chunk`` channel); the assembled content is still returned.
    """
    roles = [m.get("role", "?") for m in messages]
    last_user = next(
        (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
        "",
    )
    logger.info(
        "[%s] request model=%s temperature=%s messages=%d roles=%s stream=%s",
        log_tag,
        model,
        temperature,
        len(messages),
        roles,
        bool(on_delta) or stream,
    )
    logger.debug("[%s] last user message: %s", log_tag, truncate(last_user, 800))

    if on_delta is not None:
        parts: list[str] = []
        response_stream = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        async for chunk in response_stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta.content or ""
            if delta:
                parts.append(delta)
                try:
                    await on_delta(delta)
                except Exception as cb_exc:  # never let a UI sink break generation
                    logger.warning("[%s] on_delta callback error: %s", log_tag, cb_exc)
        content = "".join(parts)
        logger.info(
            "[%s] streamed response (%d chars): %s",
            log_tag,
            len(content),
            truncate(content, int(os.getenv("LOG_LLM_RESPONSE_MAX", "4000"))),
        )
        return content

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
