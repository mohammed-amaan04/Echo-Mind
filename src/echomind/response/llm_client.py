"""LLM client — OpenAI-compatible chat completions wrapper.

Calls ``openai/gpt-oss-20b`` via NVIDIA NIM (configurable) with low
temperature for grounded, deterministic answers.  Falls back to returning
the context summary when no API key is configured.
"""

from __future__ import annotations

import structlog

from echomind.core.config import get_settings

logger = structlog.get_logger(__name__)

# ── LLM settings ────────────────────────────────────────────────────────────

TEMPERATURE = 0.2
MAX_TOKENS = 1024


def call_llm(messages: list[dict[str, str]], fallback_answer: str = "") -> str:
    """Send messages to OpenAI chat completion and return the answer.

    Parameters
    ----------
    messages:
        Chat messages in ``[{"role": ..., "content": ...}, ...]`` format.
    fallback_answer:
        Returned if the API key is missing or the call fails.
    """
    settings = get_settings()

    if not settings.openai_api_key:
        logger.warning("openai_api_key_missing", fallback="using context summary")
        return fallback_answer or "I don't have enough information to answer that."

    try:
        from openai import OpenAI

        client = OpenAI(
            base_url=settings.llm_base_url,
            api_key=settings.openai_api_key,
        )

        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
        )

        answer = response.choices[0].message.content.strip()
        logger.info(
            "llm_call_complete",
            model=settings.openai_model,
            tokens_used=response.usage.total_tokens if response.usage else None,
        )
        return answer

    except Exception as exc:
        logger.error("llm_call_failed", error=str(exc))
        return fallback_answer or "I encountered an error generating a response."
