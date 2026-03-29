"""Response orchestrator — main entry point for the response pipeline.

Coordinates context formatting, prompt construction, LLM invocation,
confidence scoring, and action suggestions into a single call:

    ``generate_response(request) → ResponseOutput``
"""

from __future__ import annotations

import structlog

from echomind.response.actions import suggest_actions
from echomind.response.confidence import compute_confidence
from echomind.response.context_formatter import format_context
from echomind.response.llm_client import call_llm
from echomind.response.prompt_builder import build_messages
from echomind.response.schemas import ResponseOutput, ResponseRequest

logger = structlog.get_logger(__name__)

NO_CONTEXT_ANSWER = "I don't have enough information to answer that."


def generate_response(request: ResponseRequest) -> ResponseOutput:
    """Execute the full response pipeline and return a ``ResponseOutput``.

    Flow
    ----
    1. Format context (events, chunks, entities → text)
    2. Build LLM prompt
    3. Call LLM (with fallback)
    4. Compute confidence score
    5. Generate action suggestions
    6. Assemble ResponseOutput
    """
    result = request.retrieval_result

    logger.info(
        "response_start",
        query=request.query_text,
        events=len(result.relevant_events),
        entities=len(result.relevant_entities),
        chunks=len(result.supporting_chunks),
    )

    # ── Handle empty context ───────────────────────────────────────────
    if not result.relevant_events and not result.supporting_chunks:
        logger.info("response_empty_context")
        return ResponseOutput(
            answer=NO_CONTEXT_ANSWER,
            confidence_score=0.0,
        )

    # ── Step 1: Format context ─────────────────────────────────────────
    formatted = format_context(
        events=result.relevant_events,
        entities=result.relevant_entities,
        chunks=result.supporting_chunks,
    )

    # ── Step 2: Build prompt ───────────────────────────────────────────
    messages = build_messages(request.query_text, formatted)

    # ── Step 3: Call LLM ───────────────────────────────────────────────
    fallback = result.context_summary or NO_CONTEXT_ANSWER
    answer = call_llm(messages, fallback_answer=fallback)

    # ── Step 4: Confidence score ───────────────────────────────────────
    # Extract query entity names from the retrieval result entities
    query_entities = [e.name for e in result.relevant_entities]
    confidence = compute_confidence(result, query_entity_names=query_entities)

    # ── Step 5: Action suggestions ─────────────────────────────────────
    actions = suggest_actions(
        events=result.relevant_events,
        chunks=result.supporting_chunks,
    )

    # ── Step 6: Assemble output ────────────────────────────────────────
    output = ResponseOutput(
        answer=answer,
        supporting_events=[e.id for e in result.relevant_events],
        supporting_entities=[e.id for e in result.relevant_entities],
        confidence_score=confidence,
        suggested_actions=actions,
    )

    logger.info(
        "response_complete",
        confidence=confidence,
        actions=len(actions),
        answer_length=len(answer),
    )
    return output
