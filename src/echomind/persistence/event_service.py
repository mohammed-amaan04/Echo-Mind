"""Event creation service — create events when salience thresholds are met."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from echomind.db.models.event import Event
from echomind.db.models.memory import MemoryChunk
from echomind.db.models.user import UserPreferences
from echomind.persistence.logging_service import log_info, log_warning
from echomind.persistence.schemas import EventCandidate

DEFAULT_SALIENCE_THRESHOLD = 0.5


def get_salience_threshold(session: DbSession, user_id: int) -> float:
    """Retrieve the user's configured salience threshold (or the default)."""
    stmt = select(UserPreferences).where(
        UserPreferences.user_id == user_id,
        UserPreferences.pref_key == "salience_threshold",
    )
    pref = session.execute(stmt).scalar_one_or_none()
    if pref is not None:
        try:
            return float(pref.pref_value)
        except ValueError:
            log_warning(
                session,
                "event_service",
                f"Invalid salience_threshold preference value: {pref.pref_value}",
                {"user_id": user_id},
            )
    return DEFAULT_SALIENCE_THRESHOLD


def create_event_if_eligible(
    session: DbSession,
    user_id: int,
    chunk: MemoryChunk,
    event_candidate: EventCandidate | None,
    refined_salience: float,
) -> Event | None:
    """Create an event if a candidate exists and salience exceeds the user threshold."""
    if event_candidate is None:
        return None

    threshold = get_salience_threshold(session, user_id)
    if refined_salience < threshold:
        log_info(
            session,
            "event_service",
            f"Salience {refined_salience:.3f} below threshold {threshold:.3f} — skipping event",
            {"memory_chunk_id": chunk.id},
        )
        return None

    event = Event(
        user_id=user_id,
        title=event_candidate.title,
        summary=event_candidate.summary,
        event_type=event_candidate.event_type,
        start_time=chunk.timestamp,
        salience_score=refined_salience,
        created_from_chunk_id=chunk.id,
    )
    session.add(event)
    session.flush()
    log_info(
        session,
        "event_service",
        f"Created event '{event.title}' (type: {event.event_type}, salience: {refined_salience:.3f})",
        {"event_id": event.id, "memory_chunk_id": chunk.id},
    )
    return event
