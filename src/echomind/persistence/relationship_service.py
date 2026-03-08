"""Relationship linking service — build entity-event and event-memory edges."""

from __future__ import annotations

from sqlalchemy.orm import Session as DbSession

from echomind.db.models.entity import Entity
from echomind.db.models.event import Event
from echomind.db.models.link import EntityEventLink, EventMemoryLink
from echomind.persistence.entity_normalizer import normalize_entity_name
from echomind.persistence.logging_service import log_info, log_warning
from echomind.persistence.schemas import Relationship


def link_entities_to_event(
    session: DbSession,
    event: Event,
    relationships: list[Relationship],
    entity_map: dict[str, Entity],
) -> list[EntityEventLink]:
    """Create entity→event links for each relationship in the semantic output."""
    links: list[EntityEventLink] = []
    for rel in relationships:
        normalized = normalize_entity_name(rel.entity_name)
        entity = entity_map.get(normalized)
        if entity is None:
            log_warning(
                session,
                "relationship_service",
                f"Entity '{rel.entity_name}' (normalized: '{normalized}') not found for linking",
                {"event_id": event.id},
            )
            continue
        link = EntityEventLink(entity_id=entity.id, event_id=event.id, role=rel.role)
        session.add(link)
        links.append(link)

    if links:
        session.flush()
        log_info(
            session,
            "relationship_service",
            f"Created {len(links)} entity-event link(s) for event {event.id}",
            {"event_id": event.id},
        )
    return links


def link_event_to_memory(
    session: DbSession,
    event: Event,
    memory_chunk_id: int,
) -> EventMemoryLink:
    """Create an event→memory_chunk traceability link."""
    link = EventMemoryLink(event_id=event.id, memory_chunk_id=memory_chunk_id)
    session.add(link)
    session.flush()
    log_info(
        session,
        "relationship_service",
        f"Linked event {event.id} to memory chunk {memory_chunk_id}",
        {"event_id": event.id, "memory_chunk_id": memory_chunk_id},
    )
    return link
