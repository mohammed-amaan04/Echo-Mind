"""Entity-based retrieval — find events via the knowledge graph.

Maps detected entity names to ``entity_ids``, then queries
``entity_event_links`` to find events involving those entities.
When multiple entities are detected, only events containing **all** of
them are returned (intersection semantics).
"""

from __future__ import annotations

import structlog
from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from echomind.db.models.entity import Entity
from echomind.db.models.event import Event
from echomind.db.models.link import EntityEventLink
from echomind.persistence.entity_normalizer import normalize_entity_name
from echomind.retrieval.schemas import ParsedQuery

logger = structlog.get_logger(__name__)


def _resolve_entity_ids(
    session: DbSession, user_id: int, entity_names: list[str]
) -> list[int]:
    """Map display names to entity IDs via normalized name lookup."""
    ids: list[int] = []
    for name in entity_names:
        normalized = normalize_entity_name(name)
        stmt = select(Entity.id).where(
            Entity.user_id == user_id,
            Entity.normalized_name == normalized,
        )
        eid = session.execute(stmt).scalar_one_or_none()
        if eid is not None:
            ids.append(eid)
    return ids


def entity_search(
    session: DbSession,
    parsed: ParsedQuery,
    user_id: int,
) -> list[Event]:
    """Find events linked to the detected entities.

    If the query mentions multiple entities, only events connected to
    **all** of them are returned (intersection via ``HAVING COUNT``).
    Falls back to an empty list when no entities are detected.
    """
    if not parsed.detected_entities:
        return []

    entity_ids = _resolve_entity_ids(session, user_id, parsed.detected_entities)
    if not entity_ids:
        logger.info("entity_search_no_ids", detected=parsed.detected_entities)
        return []

    required_count = len(entity_ids)

    # Find event IDs linked to all detected entities
    subq = (
        select(EntityEventLink.event_id)
        .where(EntityEventLink.entity_id.in_(entity_ids))
        .group_by(EntityEventLink.event_id)
        .having(func.count(func.distinct(EntityEventLink.entity_id)) >= required_count)
        .subquery()
    )

    stmt = (
        select(Event)
        .where(Event.id.in_(select(subq.c.event_id)))
        .where(Event.user_id == user_id)
    )

    # Apply optional time filter
    if parsed.time_filter is not None:
        stmt = stmt.where(
            Event.start_time >= parsed.time_filter.start,
            Event.start_time <= parsed.time_filter.end,
        )

    stmt = stmt.order_by(Event.salience_score.desc())
    events = session.execute(stmt).scalars().all()

    logger.info(
        "entity_search_complete",
        entity_ids=entity_ids,
        events_found=len(events),
    )
    return list(events)
