"""Ranking engine — score and sort retrieval results.

Computes a composite score for each event using:
    vector_similarity (0.4) + event_salience (0.3) +
    recency (0.2) + entity_overlap (0.1)
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import structlog

from echomind.db.models.event import Event
from echomind.retrieval.schemas import ScoredChunk, ScoredEvent

logger = structlog.get_logger(__name__)

# ── Weights ──────────────────────────────────────────────────────────────────

W_VECTOR = 0.4
W_SALIENCE = 0.3
W_RECENCY = 0.2
W_ENTITY = 0.1

# Decay constant for recency score: exp(-decay * age_hours).
# 0.001 → score ≈ 0.78 after 10 days, ≈ 0.49 after 30 days.
TIME_DECAY = 0.001


def _recency_score(event_time: datetime | None) -> float:
    """Compute an exponential-decay recency score (0–1)."""
    if event_time is None:
        return 0.0
    now = datetime.now(timezone.utc)
    # Make event_time offset-aware if needed
    if event_time.tzinfo is None:
        event_time = event_time.replace(tzinfo=timezone.utc)
    age_hours = max(0.0, (now - event_time).total_seconds() / 3600.0)
    return math.exp(-TIME_DECAY * age_hours)


def _entity_overlap(
    event_entity_names: set[str],
    query_entity_names: set[str],
) -> float:
    """Fraction of query entities present in the event's linked entities."""
    if not query_entity_names:
        return 0.0
    overlap = event_entity_names & query_entity_names
    return len(overlap) / len(query_entity_names)


def rank_events(
    events: list[Event],
    event_entity_names: dict[int, set[str]],
    query_entity_names: list[str],
    chunk_scores: dict[int, float],
) -> list[ScoredEvent]:
    """Score and rank a list of events.

    Parameters
    ----------
    events:
        Candidate events to rank.
    event_entity_names:
        ``event_id → {normalized entity names}`` for overlap computation.
    query_entity_names:
        Entity names detected in the query (for overlap).
    chunk_scores:
        ``event.created_from_chunk_id → vector_similarity`` for events
        whose source chunk was found by vector search.
    """
    query_set = {n.lower() for n in query_entity_names}
    scored: list[ScoredEvent] = []

    for event in events:
        vec_sim = chunk_scores.get(event.created_from_chunk_id or -1, 0.0)
        salience = event.salience_score or 0.0
        recency = _recency_score(event.start_time)
        overlap = _entity_overlap(
            event_entity_names.get(event.id, set()),
            query_set,
        )

        composite = (
            W_VECTOR * vec_sim
            + W_SALIENCE * salience
            + W_RECENCY * recency
            + W_ENTITY * overlap
        )

        scored.append(
            ScoredEvent(
                event=event,
                score=composite,
                vector_similarity=vec_sim,
                entity_overlap=overlap,
                recency_score=recency,
            )
        )

    scored.sort(key=lambda s: s.score, reverse=True)
    logger.info("ranking_complete", events_ranked=len(scored))
    return scored


def rank_chunks(chunks: list[ScoredChunk], top_k: int) -> list[ScoredChunk]:
    """Sort scored chunks by similarity descending and truncate to top_k."""
    chunks.sort(key=lambda c: c.similarity, reverse=True)
    return chunks[:top_k]
