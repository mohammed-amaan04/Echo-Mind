"""Graph traversal — expand retrieved events into a local knowledge subgraph.

For each event, fetches all linked entities (with roles) and the supporting
memory chunks.  Optionally performs depth-1 expansion to discover related
events via shared entities.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from echomind.db.models.entity import Entity
from echomind.db.models.event import Event
from echomind.db.models.link import EntityEventLink, EventMemoryLink
from echomind.db.models.memory import MemoryChunk

logger = structlog.get_logger(__name__)


def fetch_entities_for_events(
    session: DbSession,
    event_ids: list[int],
) -> dict[int, list[Entity]]:
    """Return a mapping of ``event_id → [Entity, ...]`` for the given events."""
    if not event_ids:
        return {}

    stmt = (
        select(EntityEventLink.event_id, Entity)
        .join(Entity, Entity.id == EntityEventLink.entity_id)
        .where(EntityEventLink.event_id.in_(event_ids))
    )
    rows = session.execute(stmt).all()

    result: dict[int, list[Entity]] = {}
    for event_id, entity in rows:
        result.setdefault(event_id, []).append(entity)
    return result


def fetch_chunks_for_events(
    session: DbSession,
    event_ids: list[int],
) -> dict[int, list[MemoryChunk]]:
    """Return a mapping of ``event_id → [MemoryChunk, ...]`` via event_memory_links."""
    if not event_ids:
        return {}

    stmt = (
        select(EventMemoryLink.event_id, MemoryChunk)
        .join(MemoryChunk, MemoryChunk.id == EventMemoryLink.memory_chunk_id)
        .where(EventMemoryLink.event_id.in_(event_ids))
    )
    rows = session.execute(stmt).all()

    result: dict[int, list[MemoryChunk]] = {}
    for event_id, chunk in rows:
        result.setdefault(event_id, []).append(chunk)
    return result


def expand_graph(
    session: DbSession,
    events: list[Event],
    expand_depth: int = 1,
) -> tuple[list[Entity], list[MemoryChunk], list[Event]]:
    """Expand a set of events into their connected entities, chunks, and
    optionally related events (depth-1).

    Returns ``(all_entities, all_chunks, expanded_events)`` with duplicates
    removed.
    """
    if not events:
        return [], [], []

    event_ids = [e.id for e in events]
    seen_event_ids = set(event_ids)

    # Fetch direct links
    entity_map = fetch_entities_for_events(session, event_ids)
    chunk_map = fetch_chunks_for_events(session, event_ids)

    all_entities: dict[int, Entity] = {}
    all_chunks: dict[int, MemoryChunk] = {}
    expanded_events: list[Event] = list(events)

    for entities in entity_map.values():
        for e in entities:
            all_entities[e.id] = e

    for chunks in chunk_map.values():
        for c in chunks:
            all_chunks[c.id] = c

    # Depth-1 expansion: find other events connected to the same entities
    if expand_depth >= 1 and all_entities:
        entity_ids = list(all_entities.keys())
        stmt = (
            select(Event)
            .join(EntityEventLink, EntityEventLink.event_id == Event.id)
            .where(EntityEventLink.entity_id.in_(entity_ids))
            .where(Event.id.notin_(seen_event_ids))
            .distinct()
            .limit(20)
        )
        related = session.execute(stmt).scalars().all()
        for ev in related:
            if ev.id not in seen_event_ids:
                expanded_events.append(ev)
                seen_event_ids.add(ev.id)

    logger.info(
        "graph_expansion_complete",
        seed_events=len(events),
        total_events=len(expanded_events),
        entities=len(all_entities),
        chunks=len(all_chunks),
    )
    return list(all_entities.values()), list(all_chunks.values()), expanded_events
