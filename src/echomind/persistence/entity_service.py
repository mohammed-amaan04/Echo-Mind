"""Entity upsert service — normalize, deduplicate and persist entities."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from echomind.db.models.entity import Entity
from echomind.persistence.entity_normalizer import normalize_entity_name
from echomind.persistence.logging_service import log_info
from echomind.persistence.schemas import ExtractedEntity

# Weight applied when incrementing an existing entity's salience on re-mention.
SALIENCE_INCREMENT_WEIGHT = 0.05


def upsert_entity(
    session: DbSession,
    user_id: int,
    extracted: ExtractedEntity,
    chunk_timestamp: datetime,
    chunk_salience: float,
) -> Entity:
    """Insert a new entity or update an existing one (increment mentions)."""
    normalized = normalize_entity_name(extracted.name)

    stmt = select(Entity).where(
        Entity.user_id == user_id,
        Entity.normalized_name == normalized,
    )
    existing = session.execute(stmt).scalar_one_or_none()

    if existing is not None:
        existing.mention_count += 1
        existing.last_seen = chunk_timestamp
        existing.salience_score += chunk_salience * SALIENCE_INCREMENT_WEIGHT
        log_info(
            session,
            "entity_service",
            f"Updated entity '{existing.name}' (mentions: {existing.mention_count})",
            {"entity_id": existing.id, "normalized_name": normalized},
        )
        return existing

    entity = Entity(
        user_id=user_id,
        name=extracted.name,
        normalized_name=normalized,
        entity_type=extracted.entity_type,
        mention_count=1,
        first_seen=chunk_timestamp,
        last_seen=chunk_timestamp,
        salience_score=chunk_salience,
    )
    session.add(entity)
    session.flush()  # assigns id
    log_info(
        session,
        "entity_service",
        f"Created new entity '{entity.name}' (type: {entity.entity_type})",
        {"entity_id": entity.id, "normalized_name": normalized},
    )
    return entity


def upsert_entities(
    session: DbSession,
    user_id: int,
    entities: list[ExtractedEntity],
    chunk_timestamp: datetime,
    chunk_salience: float,
) -> dict[str, Entity]:
    """Upsert a list of entities and return a *normalized_name → Entity* map."""
    entity_map: dict[str, Entity] = {}
    for extracted in entities:
        normalized = normalize_entity_name(extracted.name)
        entity = upsert_entity(session, user_id, extracted, chunk_timestamp, chunk_salience)
        entity_map[normalized] = entity
    return entity_map
