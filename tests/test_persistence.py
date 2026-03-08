"""Phase 3 integration tests — full persistence pipeline against PostgreSQL.

Requires a running PostgreSQL instance with pgvector (use docker-compose).
Tables are created and dropped per-session to keep tests isolated.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from echomind.core.config import get_settings
from echomind.db.base import Base

# Trigger model registration
import echomind.db.models  # noqa: F401

from echomind.db.models.entity import Entity
from echomind.db.models.event import Event
from echomind.db.models.link import EntityEventLink, EventMemoryLink
from echomind.db.models.memory import MemoryChunk
from echomind.db.models.pipeline import FailedJob, ProcessingQueueEntry
from echomind.db.models.system import SystemLog
from echomind.db.models.user import User, UserPreferences
from echomind.persistence.controller import persist_semantic_output
from echomind.persistence.entity_normalizer import normalize_entity_name
from echomind.persistence.entity_service import upsert_entity
from echomind.persistence.event_service import create_event_if_eligible, get_salience_threshold
from echomind.persistence.failure_manager import escalate_if_needed
from echomind.persistence.queue_manager import mark_done, mark_failed, mark_processing
from echomind.persistence.schemas import (
    EventCandidate,
    ExtractedEntity,
    Relationship,
    SemanticOutput,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

settings = get_settings()


@pytest.fixture(scope="session")
def db_engine():
    """Create an engine and all tables once for the test session."""
    engine = create_engine(settings.database_url, future=True)
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.commit()
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)


@pytest.fixture()
def db_session(db_engine):
    """Provide a transactional session that rolls back after each test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


def _make_user(session: Session, name: str = "Test User") -> User:
    user = User(display_name=name)
    session.add(user)
    session.flush()
    return user


def _make_chunk(
    session: Session,
    user: User,
    content: str = "hello world",
    salience: float = 0.4,
    ts: datetime | None = None,
) -> MemoryChunk:
    chunk = MemoryChunk(
        user_id=user.id,
        source_type="whatsapp",
        content=content,
        timestamp=ts or datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
        participants=["Alice", "Bob"],
        initial_salience=salience,
    )
    session.add(chunk)
    session.flush()
    return chunk


def _make_queue_entry(session: Session, chunk: MemoryChunk) -> ProcessingQueueEntry:
    entry = ProcessingQueueEntry(memory_chunk_id=chunk.id, status="pending")
    session.add(entry)
    session.flush()
    return entry


# ---------------------------------------------------------------------------
# Entity upsert tests
# ---------------------------------------------------------------------------


class TestEntityUpsert:
    def test_insert_new_entity(self, db_session: Session) -> None:
        user = _make_user(db_session)
        chunk = _make_chunk(db_session, user)
        extracted = ExtractedEntity(name="EchoMind", entity_type="project")

        entity = upsert_entity(db_session, user.id, extracted, chunk.timestamp, 0.7)

        assert entity.id is not None
        assert entity.mention_count == 1
        assert entity.normalized_name == "echomind"
        assert entity.salience_score == 0.7

    def test_update_existing_entity(self, db_session: Session) -> None:
        user = _make_user(db_session)
        chunk = _make_chunk(db_session, user)
        extracted = ExtractedEntity(name="EchoMind", entity_type="project")

        entity1 = upsert_entity(db_session, user.id, extracted, chunk.timestamp, 0.7)
        entity2 = upsert_entity(db_session, user.id, extracted, chunk.timestamp, 0.8)

        assert entity1.id == entity2.id
        assert entity2.mention_count == 2
        assert entity2.salience_score == pytest.approx(0.7 + 0.8 * 0.05)

    def test_alias_resolves_to_same_entity(self, db_session: Session) -> None:
        user = _make_user(db_session)
        chunk = _make_chunk(db_session, user)

        e1 = upsert_entity(
            db_session, user.id,
            ExtractedEntity(name="Amaan", entity_type="person"),
            chunk.timestamp, 0.5,
        )
        e2 = upsert_entity(
            db_session, user.id,
            ExtractedEntity(name="Amaan Shaikh", entity_type="person"),
            chunk.timestamp, 0.5,
        )
        # Both normalize to "amaan shaikh"
        assert e1.id == e2.id
        assert e2.mention_count == 2


# ---------------------------------------------------------------------------
# Event creation tests
# ---------------------------------------------------------------------------


class TestEventCreation:
    def test_event_created_above_threshold(self, db_session: Session) -> None:
        user = _make_user(db_session)
        pref = UserPreferences(user_id=user.id, pref_key="salience_threshold", pref_value="0.5")
        db_session.add(pref)
        db_session.flush()

        chunk = _make_chunk(db_session, user)
        candidate = EventCandidate(title="Arch decision", summary="Decided on PG", event_type="decision")

        event = create_event_if_eligible(db_session, user.id, chunk, candidate, 0.75)

        assert event is not None
        assert event.title == "Arch decision"
        assert event.created_from_chunk_id == chunk.id

    def test_event_not_created_below_threshold(self, db_session: Session) -> None:
        user = _make_user(db_session)
        pref = UserPreferences(user_id=user.id, pref_key="salience_threshold", pref_value="0.5")
        db_session.add(pref)
        db_session.flush()

        chunk = _make_chunk(db_session, user)
        candidate = EventCandidate(title="Casual chat", summary="Nothing important", event_type="discussion")

        event = create_event_if_eligible(db_session, user.id, chunk, candidate, 0.3)
        assert event is None

    def test_event_not_created_without_candidate(self, db_session: Session) -> None:
        user = _make_user(db_session)
        chunk = _make_chunk(db_session, user)
        event = create_event_if_eligible(db_session, user.id, chunk, None, 0.9)
        assert event is None

    def test_default_threshold_used(self, db_session: Session) -> None:
        user = _make_user(db_session)
        threshold = get_salience_threshold(db_session, user.id)
        assert threshold == 0.5  # DEFAULT_SALIENCE_THRESHOLD


# ---------------------------------------------------------------------------
# Queue management tests
# ---------------------------------------------------------------------------


class TestQueueManager:
    def test_mark_processing(self, db_session: Session) -> None:
        user = _make_user(db_session)
        chunk = _make_chunk(db_session, user)
        entry = _make_queue_entry(db_session, chunk)

        result = mark_processing(db_session, chunk.id)
        assert result is not None
        assert result.status == "processing"

    def test_mark_done(self, db_session: Session) -> None:
        user = _make_user(db_session)
        chunk = _make_chunk(db_session, user)
        _make_queue_entry(db_session, chunk)

        mark_done(db_session, chunk.id)
        stmt = select(ProcessingQueueEntry).where(ProcessingQueueEntry.memory_chunk_id == chunk.id)
        entry = db_session.execute(stmt).scalar_one()
        assert entry.status == "done"

    def test_mark_failed_increments_retry(self, db_session: Session) -> None:
        user = _make_user(db_session)
        chunk = _make_chunk(db_session, user)
        _make_queue_entry(db_session, chunk)

        count = mark_failed(db_session, chunk.id)
        assert count == 1
        count = mark_failed(db_session, chunk.id)
        assert count == 2


# ---------------------------------------------------------------------------
# Failure escalation tests
# ---------------------------------------------------------------------------


class TestFailureManager:
    def test_no_escalation_within_limit(self, db_session: Session) -> None:
        user = _make_user(db_session)
        chunk = _make_chunk(db_session, user)
        escalated = escalate_if_needed(db_session, chunk.id, 2, "oops", "test")
        assert escalated is False

    def test_escalation_beyond_limit(self, db_session: Session) -> None:
        user = _make_user(db_session)
        chunk = _make_chunk(db_session, user)
        escalated = escalate_if_needed(db_session, chunk.id, 4, "permanent failure", "test")
        assert escalated is True

        stmt = select(FailedJob).where(FailedJob.memory_chunk_id == chunk.id)
        job = db_session.execute(stmt).scalar_one()
        assert job.failure_reason == "permanent failure"


# ---------------------------------------------------------------------------
# Full controller integration test
# ---------------------------------------------------------------------------


class TestPersistenceController:
    def test_full_pipeline_happy_path(self, db_session: Session) -> None:
        user = _make_user(db_session)
        pref = UserPreferences(user_id=user.id, pref_key="salience_threshold", pref_value="0.5")
        db_session.add(pref)
        db_session.flush()

        chunk = _make_chunk(
            db_session, user,
            content="Amaan: Let's pick PostgreSQL. Abdullah: Agreed.",
            salience=0.4,
        )
        _make_queue_entry(db_session, chunk)

        semantic = SemanticOutput(
            memory_chunk_id=chunk.id,
            entities=[
                ExtractedEntity(name="Amaan", entity_type="person"),
                ExtractedEntity(name="Abdullah", entity_type="person"),
                ExtractedEntity(name="PostgreSQL", entity_type="topic"),
            ],
            event_candidate=EventCandidate(
                title="DB selection", summary="Chose PostgreSQL", event_type="decision",
            ),
            relationships=[
                Relationship(entity_name="Amaan", role="participant"),
                Relationship(entity_name="Abdullah", role="participant"),
                Relationship(entity_name="PostgreSQL", role="subject"),
            ],
            refined_salience=0.75,
        )

        result = persist_semantic_output(db_session, semantic)

        assert result["status"] == "done"
        assert result["entities_upserted"] == 3
        assert result["event_created"] is True
        assert result["links_created"] == 3

        # Verify chunk was marked processed
        db_session.refresh(chunk)
        assert chunk.is_processed is True
        assert chunk.refined_salience == 0.75

        # Verify entities exist
        entities = db_session.execute(
            select(Entity).where(Entity.user_id == user.id)
        ).scalars().all()
        names = {e.normalized_name for e in entities}
        assert "amaan shaikh" in names  # alias resolved
        assert "abdullah khan" in names
        assert "postgresql" in names

        # Verify event created
        events = db_session.execute(
            select(Event).where(Event.user_id == user.id)
        ).scalars().all()
        assert len(events) == 1
        assert events[0].title == "DB selection"

        # Verify entity-event links
        links = db_session.execute(
            select(EntityEventLink).where(EntityEventLink.event_id == events[0].id)
        ).scalars().all()
        assert len(links) == 3

        # Verify event-memory link
        em_links = db_session.execute(
            select(EventMemoryLink).where(EventMemoryLink.event_id == events[0].id)
        ).scalars().all()
        assert len(em_links) == 1
        assert em_links[0].memory_chunk_id == chunk.id

        # Verify queue marked done
        q = db_session.execute(
            select(ProcessingQueueEntry).where(
                ProcessingQueueEntry.memory_chunk_id == chunk.id
            )
        ).scalar_one()
        assert q.status == "done"

    def test_no_event_when_below_threshold(self, db_session: Session) -> None:
        user = _make_user(db_session)
        pref = UserPreferences(user_id=user.id, pref_key="salience_threshold", pref_value="0.5")
        db_session.add(pref)
        db_session.flush()

        chunk = _make_chunk(db_session, user, content="Casual chat about weather")
        _make_queue_entry(db_session, chunk)

        semantic = SemanticOutput(
            memory_chunk_id=chunk.id,
            entities=[ExtractedEntity(name="Weather", entity_type="topic")],
            event_candidate=EventCandidate(
                title="Weather chat", summary="Talked about rain", event_type="discussion",
            ),
            relationships=[Relationship(entity_name="Weather", role="subject")],
            refined_salience=0.3,
        )

        result = persist_semantic_output(db_session, semantic)

        assert result["status"] == "done"
        assert result["event_created"] is False
        assert result["links_created"] == 0

    def test_system_logs_created(self, db_session: Session) -> None:
        user = _make_user(db_session)
        chunk = _make_chunk(db_session, user)
        _make_queue_entry(db_session, chunk)

        semantic = SemanticOutput(
            memory_chunk_id=chunk.id,
            entities=[ExtractedEntity(name="Test", entity_type="topic")],
            refined_salience=0.2,
        )
        persist_semantic_output(db_session, semantic)

        logs = db_session.execute(select(SystemLog)).scalars().all()
        assert len(logs) > 0
        modules = {log.module for log in logs}
        assert "entity_service" in modules or "queue_manager" in modules
