"""Context builder — assemble the final RetrievalResult.

Collects top-ranked events, their linked entities, and supporting memory
chunks.  Deduplicates, sorts chronologically, and generates a plain-text
``context_summary`` suitable for LLM consumption in Phase 5.
"""

from __future__ import annotations

from echomind.db.models.entity import Entity
from echomind.db.models.event import Event
from echomind.db.models.memory import MemoryChunk
from echomind.retrieval.schemas import RetrievalResult, ScoredChunk, ScoredEvent


def _format_event(event: Event, entities: list[Entity]) -> str:
    """Format a single event into a readable context line."""
    parts: list[str] = []

    # Title and type
    date_str = event.start_time.strftime("%Y-%m-%d %H:%M") if event.start_time else "Unknown"
    parts.append(f"- Event: {event.title} ({event.event_type}, {date_str})")

    # Participants
    if entities:
        names = ", ".join(e.name for e in entities)
        parts.append(f"  Participants: {names}")

    # Summary
    if event.summary:
        parts.append(f"  Summary: {event.summary}")

    return "\n".join(parts)


def build_context(
    scored_events: list[ScoredEvent],
    all_entities: list[Entity],
    graph_chunks: list[MemoryChunk],
    vector_chunks: list[ScoredChunk],
    event_entity_map: dict[int, list[Entity]],
    top_k: int = 10,
) -> RetrievalResult:
    """Build the final ``RetrievalResult`` from ranked components.

    Parameters
    ----------
    scored_events:
        Events ranked by the scoring engine.
    all_entities:
        All entities discovered via graph expansion.
    graph_chunks:
        Memory chunks linked to events via ``event_memory_links``.
    vector_chunks:
        Memory chunks from vector similarity search.
    event_entity_map:
        ``event_id → [Entity, ...]`` for context formatting.
    top_k:
        Maximum number of events / chunks to include.
    """
    # ── Top events (sorted chronologically for context coherence) ──────
    top_events_scored = scored_events[:top_k]
    top_events = [se.event for se in top_events_scored]
    top_events.sort(key=lambda e: e.start_time or e.created_at)

    # ── Deduplicated entities ──────────────────────────────────────────
    seen_entity_ids: set[int] = set()
    unique_entities: list[Entity] = []
    for entity in all_entities:
        if entity.id not in seen_entity_ids:
            seen_entity_ids.add(entity.id)
            unique_entities.append(entity)

    # ── Deduplicated supporting chunks ─────────────────────────────────
    seen_chunk_ids: set[int] = set()
    unique_chunks: list[MemoryChunk] = []

    # Graph-linked chunks first (direct evidence)
    for chunk in graph_chunks:
        if chunk.id not in seen_chunk_ids:
            seen_chunk_ids.add(chunk.id)
            unique_chunks.append(chunk)

    # Then vector-matched chunks
    for sc in vector_chunks:
        if sc.chunk.id not in seen_chunk_ids:
            seen_chunk_ids.add(sc.chunk.id)
            unique_chunks.append(sc.chunk)

    unique_chunks = unique_chunks[:top_k]
    unique_chunks.sort(key=lambda c: c.timestamp)

    # ── Context summary (plain text for LLM input) ─────────────────────
    summary_lines: list[str] = []
    for event in top_events:
        linked = event_entity_map.get(event.id, [])
        summary_lines.append(_format_event(event, linked))

    context_summary = "\n".join(summary_lines) if summary_lines else "No relevant events found."

    return RetrievalResult(
        relevant_events=top_events,
        relevant_entities=unique_entities,
        supporting_chunks=unique_chunks,
        context_summary=context_summary,
    )
