"""Confidence scoring — estimate answer reliability.

Computes a 0–1 confidence score based on:
    context_density (0.4) + entity_match (0.3) + event_salience (0.3)
"""

from __future__ import annotations

from echomind.retrieval.schemas import RetrievalResult


def compute_confidence(
    retrieval_result: RetrievalResult,
    query_entity_names: list[str] | None = None,
) -> float:
    """Compute a confidence score for the response.

    Parameters
    ----------
    retrieval_result:
        The retrieval output used to generate the answer.
    query_entity_names:
        Entity names detected in the query (from query parser).
        If None, entity_match defaults to 0.
    """
    events = retrieval_result.relevant_events
    entities = retrieval_result.relevant_entities

    # ── Context density (how much data backs the answer) ─────────────
    # Score reaches 1.0 at 3+ events
    context_density = min(1.0, len(events) / 3.0) if events else 0.0

    # ── Entity match (fraction of query entities found) ──────────────
    entity_match = 0.0
    if query_entity_names:
        found_names = {e.name.lower() for e in entities}
        query_set = {n.lower() for n in query_entity_names}
        if query_set:
            matched = sum(1 for q in query_set if any(q in f for f in found_names))
            entity_match = matched / len(query_set)

    # ── Event relevance (average salience of returned events) ────────
    event_salience = 0.0
    if events:
        saliences = [e.salience_score for e in events if e.salience_score]
        event_salience = sum(saliences) / len(saliences) if saliences else 0.0

    # ── Composite score ──────────────────────────────────────────────
    confidence = (
        0.4 * context_density
        + 0.3 * entity_match
        + 0.3 * event_salience
    )

    return round(min(1.0, max(0.0, confidence)), 3)
