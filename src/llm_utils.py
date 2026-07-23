"""LLM and embedding helpers with retry, rate-limit handling, and local fallbacks."""

import logging
import random
import time
from typing import Any, Callable, Optional, TypeVar

import config

logger = logging.getLogger(__name__)

T = TypeVar("T")

OPENAI_RATE_LIMIT_MARKERS = (
    "rate_limit",
    "rate limit",
    "429",
    "quota",
    "insufficient_quota",
    "billing",
    "too many requests",
    "openai.http_status.429",
    "openai.error.rate_limit",
    "openai.AuthenticationError",
    "openai.APIError",
)


def is_rate_limit_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in OPENAI_RATE_LIMIT_MARKERS)


def call_with_retry(
    fn: Callable[[], T],
    *,
    max_attempts: int = None,
    base_delay: float = None,
    label: str = "LLM call",
) -> T:
    max_attempts = max_attempts or config.LLM_MAX_RETRIES
    base_delay = base_delay or config.LLM_RETRY_BASE_DELAY
    last_error: Optional[Exception] = None

    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:
            last_error = exc
            if attempt >= max_attempts or not is_rate_limit_error(exc):
                raise
            jitter = random.uniform(0, base_delay * 0.5)
            delay = (base_delay * (2 ** (attempt - 1))) + jitter
            logger.warning(
                "%s hit rate limit (attempt %s/%s). Retrying in %.1fs: %s",
                label,
                attempt,
                max_attempts,
                delay,
                exc,
            )
            time.sleep(delay)

    raise last_error  # pragma: no cover


def complete_with_fallback(
    llm: Any,
    prompt: str,
    *,
    mode: str = None,
    label: str = "generation",
) -> str:
    """Complete a prompt, falling back to local Ollama when cloud limits are hit."""

    def _complete(active_llm: Any) -> str:
        response = call_with_retry(
            lambda: active_llm.complete(prompt),
            label=label,
        )
        return response.text.strip()

    try:
        return _complete(llm)
    except Exception as exc:
        mode = mode or config.config.mode
        if mode != "cloud" or not is_rate_limit_error(exc):
            raise

        logger.warning("Cloud LLM unavailable (%s). Falling back to local Ollama.", exc)
        from src.retrieval import get_llm

        try:
            local_llm = get_llm("local")
            return _complete(local_llm)
        except Exception as local_exc:
            logger.error("Local fallback also failed: %s", local_exc)
            raise RuntimeError(
                f"Cloud LLM failed ({exc}) and local fallback failed ({local_exc}). "
                "Check Ollama availability or switch modes."
            ) from local_exc
