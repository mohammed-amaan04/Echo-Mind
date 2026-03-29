"""Query understanding module — parse and classify user queries.

Cleans query text, detects referenced entities via keyword matching against
the ``entities`` table, classifies intent, and extracts time filters.
No spaCy dependency — uses pure SQL + regex for speed.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from echomind.db.models.entity import Entity
from echomind.persistence.entity_normalizer import normalize_entity_name
from echomind.retrieval.schemas import ParsedQuery, TimeRange

# ── Time expression patterns ────────────────────────────────────────────────

_TIME_PATTERNS: list[tuple[str, int]] = [
    (r"\btoday\b", 1),
    (r"\byesterday\b", 2),
    (r"\blast\s+week\b", 7),
    (r"\bthis\s+week\b", 7),
    (r"\brecent(?:ly)?\b", 7),
    (r"\blast\s+month\b", 30),
    (r"\blast\s+(\d+)\s+days?\b", 0),  # dynamic — group(1) is the count
]


def _extract_time_filter(text: str) -> TimeRange | None:
    """Return a ``TimeRange`` if the query contains a recognisable time cue."""
    now = datetime.now(timezone.utc)
    lower = text.lower()

    for pattern, default_days in _TIME_PATTERNS:
        match = re.search(pattern, lower)
        if match:
            days = int(match.group(1)) if match.lastindex else default_days
            return TimeRange(start=now - timedelta(days=days), end=now)
    return None


def _detect_entities(session: DbSession, user_id: int, text: str) -> list[str]:
    """Match query text against known entity names for the user.

    Uses word-level overlap: if *any* word from the entity's normalized name
    appears in the query (after normalization), the entity is considered
    detected.  This handles alias-expanded names like ``amaan shaikh``
    matching a query that only mentions ``amaan``.

    Returns the canonical (display) names of matched entities.
    """
    normalized_query = normalize_entity_name(text)
    query_words = set(normalized_query.split())

    # Fetch all entity names for the user (typically a small set)
    stmt = select(Entity).where(Entity.user_id == user_id)
    entities = session.execute(stmt).scalars().all()

    matched: list[str] = []
    seen: set[int] = set()
    for entity in entities:
        if entity.id in seen:
            continue
        entity_words = set(entity.normalized_name.split())
        # Match if any word from the entity name appears in query words
        if entity_words & query_words:
            matched.append(entity.name)
            seen.add(entity.id)

    return matched


def _classify_intent(text: str, detected_entities: list[str]) -> str:
    """Classify the query intent based on keywords and entity count."""
    lower = text.lower()

    # Temporal signals
    temporal_cues = [
        "recent", "yesterday", "today", "last week", "this week",
        "last month", "when", "timeline",
    ]
    if any(cue in lower for cue in temporal_cues):
        return "temporal"

    # Relational: query references 2+ entities
    if len(detected_entities) >= 2:
        return "relational"

    return "informational"


def parse_query(session: DbSession, query: str, user_id: int) -> ParsedQuery:
    """Parse raw query text into a structured ``ParsedQuery``."""
    cleaned = query.strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    detected = _detect_entities(session, user_id, cleaned)
    intent = _classify_intent(cleaned, detected)
    time_filter = _extract_time_filter(cleaned)

    return ParsedQuery(
        cleaned_query=cleaned,
        detected_entities=detected,
        intent_type=intent,
        time_filter=time_filter,
    )
