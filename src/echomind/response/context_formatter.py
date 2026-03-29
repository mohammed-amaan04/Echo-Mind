"""Context formatter — prepare retrieval data for LLM consumption.

Formats events, entities, and chunks into clean, token-efficient text
suitable for inclusion in an LLM prompt.
"""

from __future__ import annotations

from dataclasses import dataclass

from echomind.db.models.entity import Entity
from echomind.db.models.event import Event
from echomind.db.models.memory import MemoryChunk

MAX_CHUNKS = 8
MAX_CHUNK_CHARS = 300


@dataclass
class FormattedContext:
    """LLM-ready text representations of retrieval data."""

    events_text: str
    chunks_text: str
    entity_list: str


def _format_event(event: Event) -> str:
    """Format a single event into a concise summary line."""
    date_str = event.start_time.strftime("%Y-%m-%d") if event.start_time else "unknown date"
    parts = [f"[{event.event_type}] {event.title} ({date_str})"]
    if event.summary:
        parts.append(f"  → {event.summary}")
    return "\n".join(parts)


def _format_chunk(chunk: MemoryChunk, index: int) -> str:
    """Format a single chunk with truncation."""
    content = chunk.content
    if len(content) > MAX_CHUNK_CHARS:
        content = content[:MAX_CHUNK_CHARS] + "…"
    source = chunk.source_type or "unknown"
    return f"[{index + 1}] ({source}) {content}"


def format_context(
    events: list[Event],
    entities: list[Entity],
    chunks: list[MemoryChunk],
) -> FormattedContext:
    """Format retrieval data into structured text for the LLM prompt.

    Events are sorted chronologically, chunks are truncated and capped
    at ``MAX_CHUNKS``, entities are listed with type annotations.
    """
    # Events — chronological
    sorted_events = sorted(events, key=lambda e: e.start_time or e.created_at)
    events_text = "\n".join(_format_event(e) for e in sorted_events)
    if not events_text:
        events_text = "No relevant events found."

    # Chunks — truncated, capped
    capped_chunks = chunks[:MAX_CHUNKS]
    chunks_text = "\n".join(_format_chunk(c, i) for i, c in enumerate(capped_chunks))
    if not chunks_text:
        chunks_text = "No supporting evidence available."

    # Entities — simple list
    entity_parts = [f"{e.name} ({e.entity_type})" for e in entities]
    entity_list = ", ".join(entity_parts) if entity_parts else "None detected"

    return FormattedContext(
        events_text=events_text,
        chunks_text=chunks_text,
        entity_list=entity_list,
    )
