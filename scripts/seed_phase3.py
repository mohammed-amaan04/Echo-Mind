"""Seed Phase 3 dummy data for independent testing.

Populates the database with:
  - A test user and salience-threshold preference
  - Dummy memory chunks simulating real conversations
  - Processing-queue entries (status=pending) for each chunk
  - Example SemanticOutput objects fed through the persistence controller

Run:
    python -m scripts.seed_phase3          (from project root, with src on PYTHONPATH)
    or: python scripts/seed_phase3.py      (adjust PYTHONPATH/sys.path as needed)
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure src/ is importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from echomind.db.base import Base
from echomind.db.models import *  # noqa: F401,F403 — registers all models
from echomind.db.models.memory import MemoryChunk
from echomind.db.models.pipeline import ProcessingQueueEntry
from echomind.db.models.user import User, UserPreferences
from echomind.db.session import SessionLocal, engine
from echomind.persistence.controller import persist_semantic_output
from echomind.persistence.schemas import (
    EventCandidate,
    ExtractedEntity,
    Relationship,
    SemanticOutput,
)


def _ts(day: int, hour: int = 10) -> datetime:
    """Helper to create a timezone-aware timestamp in March 2026."""
    return datetime(2026, 3, day, hour, 0, 0, tzinfo=timezone.utc)


DUMMY_CHUNKS = [
    {
        "source_type": "whatsapp",
        "content": (
            "Amaan: Let's finalize the EchoMind architecture today. "
            "Abdullah: Agreed, we should lock down the schema before coding. "
            "Abrar: I'll prepare the ER diagram."
        ),
        "timestamp": _ts(1, 10),
        "participants": ["Amaan", "Abdullah", "Abrar"],
        "initial_salience": 0.4,
    },
    {
        "source_type": "whatsapp",
        "content": (
            "Abrar: Should we use PostgreSQL or MongoDB? "
            "Amaan: PostgreSQL with pgvector gives us both relational and vector support. "
            "Abdullah: Makes sense for the knowledge graph."
        ),
        "timestamp": _ts(1, 14),
        "participants": ["Amaan", "Abdullah", "Abrar"],
        "initial_salience": 0.5,
    },
    {
        "source_type": "gmail",
        "content": (
            "Subject: EchoMind Sprint 1 deadlines\n"
            "Hi team, please complete the preprocessing pipeline by March 10. "
            "Amaan will handle the semantic layer. "
            "Abrar covers ingestion. Abdullah does the persistence layer. "
            "Best, Amaan"
        ),
        "timestamp": _ts(2, 9),
        "participants": ["Amaan", "Abrar", "Abdullah"],
        "initial_salience": 0.6,
    },
    {
        "source_type": "voice_note",
        "content": (
            "Meeting notes: We discussed the salience scoring algorithm. "
            "Decisions should always have high salience. "
            "Casual chatter has low salience."
        ),
        "timestamp": _ts(3, 16),
        "participants": ["Amaan"],
        "initial_salience": 0.3,
    },
    {
        "source_type": "whatsapp",
        "content": (
            "Abdullah: The schema migration is ready. "
            "Amaan: Great, let's run it on the staging DB. "
            "Abrar: I'll hook up the WhatsApp connector tonight."
        ),
        "timestamp": _ts(5, 20),
        "participants": ["Amaan", "Abdullah", "Abrar"],
        "initial_salience": 0.45,
    },
]

# Corresponding SemanticOutputs (will be populated after chunks are inserted)
SEMANTIC_TEMPLATES = [
    {
        "entities": [
            ExtractedEntity(name="Amaan", entity_type="person"),
            ExtractedEntity(name="Abdullah", entity_type="person"),
            ExtractedEntity(name="Abrar", entity_type="person"),
            ExtractedEntity(name="EchoMind", entity_type="project"),
        ],
        "event_candidate": EventCandidate(
            title="EchoMind architecture finalization",
            summary="Team agreed to lock down the schema before coding begins.",
            event_type="decision",
        ),
        "relationships": [
            Relationship(entity_name="Amaan", role="participant"),
            Relationship(entity_name="Abdullah", role="participant"),
            Relationship(entity_name="Abrar", role="participant"),
            Relationship(entity_name="EchoMind", role="subject"),
        ],
        "refined_salience": 0.72,
    },
    {
        "entities": [
            ExtractedEntity(name="Abrar", entity_type="person"),
            ExtractedEntity(name="Amaan", entity_type="person"),
            ExtractedEntity(name="Abdullah", entity_type="person"),
            ExtractedEntity(name="PostgreSQL", entity_type="topic"),
            ExtractedEntity(name="MongoDB", entity_type="topic"),
        ],
        "event_candidate": EventCandidate(
            title="Database selection — PostgreSQL chosen",
            summary="Team chose PostgreSQL with pgvector over MongoDB for relational + vector support.",
            event_type="decision",
        ),
        "relationships": [
            Relationship(entity_name="Amaan", role="participant"),
            Relationship(entity_name="Abdullah", role="participant"),
            Relationship(entity_name="Abrar", role="participant"),
            Relationship(entity_name="PostgreSQL", role="subject"),
        ],
        "refined_salience": 0.81,
    },
    {
        "entities": [
            ExtractedEntity(name="Amaan", entity_type="person"),
            ExtractedEntity(name="Abrar", entity_type="person"),
            ExtractedEntity(name="Abdullah", entity_type="person"),
            ExtractedEntity(name="EchoMind", entity_type="project"),
        ],
        "event_candidate": EventCandidate(
            title="Sprint 1 deadline set — March 10",
            summary="Preprocessing pipeline due March 10. Roles assigned: Amaan=semantic, Abrar=ingestion, Abdullah=persistence.",
            event_type="task",
        ),
        "relationships": [
            Relationship(entity_name="Amaan", role="organizer"),
            Relationship(entity_name="Abrar", role="participant"),
            Relationship(entity_name="Abdullah", role="participant"),
            Relationship(entity_name="EchoMind", role="subject"),
        ],
        "refined_salience": 0.78,
    },
    {
        "entities": [
            ExtractedEntity(name="Amaan", entity_type="person"),
        ],
        "event_candidate": EventCandidate(
            title="Salience scoring discussion",
            summary="Discussed how to compute salience. Decisions get high scores, casual chat gets low.",
            event_type="discussion",
        ),
        "relationships": [
            Relationship(entity_name="Amaan", role="participant"),
        ],
        "refined_salience": 0.35,  # below threshold — should NOT create an event
    },
    {
        "entities": [
            ExtractedEntity(name="Abdullah", entity_type="person"),
            ExtractedEntity(name="Amaan", entity_type="person"),
            ExtractedEntity(name="Abrar", entity_type="person"),
        ],
        "event_candidate": EventCandidate(
            title="Schema migration ready for staging",
            summary="Abdullah completed the migration; Abrar to connect WhatsApp connector.",
            event_type="task",
        ),
        "relationships": [
            Relationship(entity_name="Abdullah", role="participant"),
            Relationship(entity_name="Amaan", role="participant"),
            Relationship(entity_name="Abrar", role="participant"),
        ],
        "refined_salience": 0.65,
    },
]


def seed() -> None:
    """Create tables (if missing) and run the full Phase 3 seeding pipeline."""
    # Create all tables — idempotent, safe during development
    Base.metadata.create_all(engine)

    session = SessionLocal()
    try:
        # ── 1. Create test user ──────────────────────────────────────
        user = User(display_name="Amaan Shaikh", email="amaan@echomind.dev")
        session.add(user)
        session.flush()
        print(f"[seed] Created user id={user.id}")

        # ── 2. Set salience threshold preference ─────────────────────
        pref = UserPreferences(
            user_id=user.id, pref_key="salience_threshold", pref_value="0.5"
        )
        session.add(pref)
        session.flush()
        print(f"[seed] salience_threshold = 0.5")

        # ── 3. Insert dummy memory chunks + queue entries ────────────
        chunk_ids: list[int] = []
        for i, data in enumerate(DUMMY_CHUNKS):
            chunk = MemoryChunk(
                user_id=user.id,
                source_type=data["source_type"],
                content=data["content"],
                timestamp=data["timestamp"],
                participants=data["participants"],
                initial_salience=data["initial_salience"],
            )
            session.add(chunk)
            session.flush()
            chunk_ids.append(chunk.id)

            queue_entry = ProcessingQueueEntry(memory_chunk_id=chunk.id, status="pending")
            session.add(queue_entry)
            print(f"[seed] Chunk {i + 1}/{len(DUMMY_CHUNKS)} → id={chunk.id}")

        session.commit()
        print(f"[seed] Inserted {len(chunk_ids)} chunks + queue entries\n")

        # ── 4. Run persistence controller for each chunk ─────────────
        for idx, (chunk_id, tpl) in enumerate(zip(chunk_ids, SEMANTIC_TEMPLATES)):
            semantic = SemanticOutput(
                memory_chunk_id=chunk_id,
                entities=tpl["entities"],
                event_candidate=tpl["event_candidate"],
                relationships=tpl["relationships"],
                refined_salience=tpl["refined_salience"],
            )
            print(f"[persist] Processing chunk {chunk_id} "
                  f"(salience={tpl['refined_salience']:.2f})...")
            result = persist_semantic_output(session, semantic)
            print(f"  → status={result['status']}, "
                  f"entities={result['entities_upserted']}, "
                  f"event={result['event_created']}, "
                  f"links={result['links_created']}")

        print("\n[seed] Phase 3 seeding complete.")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed()
