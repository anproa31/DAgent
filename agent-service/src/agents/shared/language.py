"""Detect the response language the user expects (ISO 639-1), fully offline.

Uses ``lingua`` (statistical n-gram detector) instead of an LLM call: no extra
round-trip, no network, no provider/structured-output dependency, and far more
reliable on the short text typical of analytics queries.
"""

from __future__ import annotations

import re
from functools import lru_cache

from lingua import LanguageDetectorBuilder

from utils.agent_logger import get_logger

logger = get_logger("language")

DEFAULT_LANGUAGE = "en"

# Below this many alphabetic characters the text is too short to classify
# reliably (e.g. "ok", "top 10") — fall back to the default instead of guessing.
_MIN_ALPHA_CHARS = 3


@lru_cache(maxsize=1)
def _detector():
    """Build the detector once. ``low_accuracy_mode`` bounds memory while still
    beating langid/langdetect on short text. Loaded lazily on first detection."""
    return LanguageDetectorBuilder.from_all_languages().with_low_accuracy_mode().build()


def normalize_language_code(code: str | None) -> str:
    """Normalize to a lowercase 2-letter ISO 639-1 code, defaulting to English."""
    if not code:
        return DEFAULT_LANGUAGE
    cleaned = re.sub(r"[^a-z]", "", code.strip().lower())
    return cleaned[:2] if len(cleaned) >= 2 else DEFAULT_LANGUAGE


def language_response_rule(language: str) -> str:
    """Prompt fragment forcing user-facing prose into the detected language."""
    lang = normalize_language_code(language)
    return (
        "RESPONSE LANGUAGE (mandatory): Write ALL user-facing prose in the language "
        f"with ISO 639-1 code '{lang}'. SQL, Python, and code identifiers stay in English. "
        "Keep technical terms untranslated when no accurate equivalent exists."
    )


def detect_response_language(query: str) -> str:
    """Detect the language the user expects for the assistant's reply.

    Synchronous and CPU-bound (a few ms once warm); call it via
    ``asyncio.to_thread`` from async code so the first, model-loading call does
    not block the event loop.
    """
    text = (query or "").strip()
    if sum(c.isalpha() for c in text) < _MIN_ALPHA_CHARS:
        return DEFAULT_LANGUAGE

    try:
        language = _detector().detect_language_of(text)
        if language is None:
            return DEFAULT_LANGUAGE
        code = normalize_language_code(language.iso_code_639_1.name)
        logger.info("detected response language=%s query=%r", code, text[:80])
        return code
    except Exception as exc:
        logger.warning("language detection failed, defaulting to %s: %s", DEFAULT_LANGUAGE, exc)
        return DEFAULT_LANGUAGE
