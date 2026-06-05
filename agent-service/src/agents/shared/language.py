"""Detect the response language the user expects (ISO 639-1)."""

from __future__ import annotations

import re

from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from agents.shared.llm_endpoint import normalize_base_url
from utils.agent_logger import get_logger

logger = get_logger("language")

DEFAULT_LANGUAGE = "en"

_LANGUAGE_DETECTION_SYSTEM = (
    "You are a fast language classifier. Analyze the user's message and determine "
    "the primary language they want the assistant's answer written in — even when "
    "they mix languages. Return only the ISO 639-1 code (e.g. vi, en, fr, ja, zh)."
)


class LanguageDetection(BaseModel):
    language: str = Field(description="ISO 639-1 language code (e.g. 'vi', 'en')")


def normalize_language_code(code: str | None) -> str:
    """Normalize to a lowercase ISO 639-1 code, falling back to English."""
    if not code:
        return DEFAULT_LANGUAGE
    cleaned = re.sub(r"[^a-zA-Z]", "", code.strip().lower())
    if len(cleaned) >= 2:
        return cleaned[:2]
    return DEFAULT_LANGUAGE


def language_response_rule(language: str) -> str:
    """Prompt fragment forcing user-facing prose into the detected language."""
    lang = normalize_language_code(language)
    return (
        f"RESPONSE LANGUAGE (mandatory): Write ALL user-facing prose in the language "
        f"with ISO 639-1 code '{lang}'. SQL, Python, and code identifiers stay in English. "
        f"Keep technical terms untranslated when no accurate equivalent exists."
    )


async def detect_response_language(
    query: str,
    *,
    base_url: str,
    api_key: str,
    model: str,
) -> str:
    """Detect the language the user expects for the assistant's reply."""
    text = (query or "").strip()
    if not text:
        return DEFAULT_LANGUAGE

    try:
        llm = ChatOpenAI(
            model=model,
            temperature=0,
            base_url=normalize_base_url(base_url),
            api_key=api_key or "none",
        )
        structured_llm = llm.with_structured_output(LanguageDetection)
        result = await structured_llm.ainvoke(
            [
                ("system", _LANGUAGE_DETECTION_SYSTEM),
                ("user", text),
            ]
        )
        language = normalize_language_code(getattr(result, "language", None))
        logger.info("detected response language=%s query=%r", language, text[:80])
        return language
    except Exception as exc:
        logger.warning("language detection failed, defaulting to %s: %s", DEFAULT_LANGUAGE, exc)
        return DEFAULT_LANGUAGE
