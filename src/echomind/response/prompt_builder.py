"""Prompt builder — construct LLM-ready prompts from formatted context.

Builds a system + user message pair for OpenAI chat completion,
ensuring the model stays grounded in the provided context.
"""

from __future__ import annotations

from echomind.response.context_formatter import FormattedContext

SYSTEM_PROMPT = """\
You are EchoMind, a personal cognitive memory assistant.

RULES:
- Answer ONLY using the provided context below.
- DO NOT make up facts, names, dates, or events not in the context.
- If the answer is not in the context, say "I don't have enough information to answer that."
- Be concise, factual, and structured.
- Reference specific events or conversations when possible.\
"""

USER_PROMPT_TEMPLATE = """\
User Query:
{query}

Known Entities:
{entities}

Events:
{events}

Evidence:
{chunks}

Answer:\
"""


def build_messages(
    query: str,
    context: FormattedContext,
) -> list[dict[str, str]]:
    """Build the chat message list for OpenAI's chat completion API.

    Returns a list of ``{"role": ..., "content": ...}`` dicts.
    """
    user_content = USER_PROMPT_TEMPLATE.format(
        query=query,
        entities=context.entity_list,
        events=context.events_text,
        chunks=context.chunks_text,
    )

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]
