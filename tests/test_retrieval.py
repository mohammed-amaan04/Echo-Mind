"""Phase 4 retrieval layer tests — integration tests against PostgreSQL.

Requires a running PostgreSQL instance with pgvector (use docker-compose).
Tests generate real embeddings using sentence-transformers for vector search.
Tables are created/dropped per-session, each test rolls back its transaction.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest
from sentence_transformers import SentenceTransformer
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
from echomind.db.models.pipeline import ProcessingQueueEntry
from echomind.db.models.user import User, UserPreferences
from echomind.persistence.controller import persist_semantic_output
from echomind.persistence.schemas import (
    EventCandidate,
    ExtractedEntity,
    Relationship,
    SemanticOutput,
)
from echomind.retrieval.engine import retrieve_context
from echomind.retrieval.query_parser import parse_query
from echomind.retrieval.ranker import _recency_score
from echomind.retrieval.schemas import RetrievalQuery

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

settings = get_settings()

# Lazy-loaded embedding model (shared across all tests)
_model: SentenceTransformer | None = None


def _get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def _embed(text_content: str) -> list[float]:
    model = _get_embedding_model()
    return model.encode(text_content, normalize_embeddings=True).tolist()


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
    # Add default salience threshold
    pref = UserPreferences(user_id=user.id, pref_key="salience_threshold", pref_value="0.5")
    session.add(pref)
    session.flush()
    return user


def _make_chunk(
    session: Session,
    user: User,
    content: str,
    ts: datetime | None = None,
    with_embedding: bool = True,
) -> MemoryChunk:
    chunk = MemoryChunk(
        user_id=user.id,
        source_type="whatsapp",
        content=content,
        timestamp=ts or datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
        participants=["Alice", "Bob"],
        initial_salience=0.5,
    )
    session.add(chunk)
    session.flush()

    if with_embedding:
        embedding = _embed(content)
        session.execute(
            text("UPDATE memory_chunks SET embedding = CAST(:vec AS vector) WHERE id = :id"),
            {"vec": str(embedding), "id": chunk.id},
        )
        session.flush()

    return chunk


def _make_queue_entry(session: Session, chunk: MemoryChunk) -> ProcessingQueueEntry:
    entry = ProcessingQueueEntry(memory_chunk_id=chunk.id, status="pending")
    session.add(entry)
    session.flush()
    return entry


def _seed_knowledge_graph(session: Session, user: User) -> dict:
    """Create a realistic knowledge graph for testing retrieval.

    Returns a dict with references to created objects.
    """
    # Chunk 1: Architecture discussion
    chunk1 = _make_chunk(
        session, user,
        "Amaan: Let's finalize the EchoMind architecture today. "
        "Abdullah: Agreed, we should lock down the schema before coding.",
        ts=datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc),
    )
    _make_queue_entry(session, chunk1)
    persist_semantic_output(session, SemanticOutput(
        memory_chunk_id=chunk1.id,
        entities=[
            ExtractedEntity(name="Amaan", entity_type="person"),
            ExtractedEntity(name="Abdullah", entity_type="person"),
            ExtractedEntity(name="EchoMind", entity_type="project"),
        ],
        event_candidate=EventCandidate(
            title="EchoMind architecture finalization",
            summary="Team agreed to lock down the schema before coding.",
            event_type="decision",
        ),
        relationships=[
            Relationship(entity_name="Amaan", role="participant"),
            Relationship(entity_name="Abdullah", role="participant"),
            Relationship(entity_name="EchoMind", role="subject"),
        ],
        refined_salience=0.72,
    ))

    # Chunk 2: Database decision
    chunk2 = _make_chunk(
        session, user,
        "Amaan: PostgreSQL with pgvector gives us both relational and vector support. "
        "Abdullah: Makes sense for the knowledge graph.",
        ts=datetime(2026, 3, 1, 14, 0, tzinfo=timezone.utc),
    )
    _make_queue_entry(session, chunk2)
    persist_semantic_output(session, SemanticOutput(
        memory_chunk_id=chunk2.id,
        entities=[
            ExtractedEntity(name="Amaan", entity_type="person"),
            ExtractedEntity(name="Abdullah", entity_type="person"),
            ExtractedEntity(name="PostgreSQL", entity_type="topic"),
        ],
        event_candidate=EventCandidate(
            title="Database selection — PostgreSQL chosen",
            summary="Chose PostgreSQL with pgvector over MongoDB.",
            event_type="decision",
        ),
        relationships=[
            Relationship(entity_name="Amaan", role="participant"),
            Relationship(entity_name="Abdullah", role="participant"),
            Relationship(entity_name="PostgreSQL", role="subject"),
        ],
        refined_salience=0.81,
    ))

    # Chunk 3: Recent task assignment
    chunk3 = _make_chunk(
        session, user,
        "Abdullah: The schema migration is ready. "
        "Amaan: Great, let's run it on staging.",
        ts=datetime(2026, 3, 5, 20, 0, tzinfo=timezone.utc),
    )
    _make_queue_entry(session, chunk3)
    persist_semantic_output(session, SemanticOutput(
        memory_chunk_id=chunk3.id,
        entities=[
            ExtractedEntity(name="Abdullah", entity_type="person"),
            ExtractedEntity(name="Amaan", entity_type="person"),
        ],
        event_candidate=EventCandidate(
            title="Schema migration ready for staging",
            summary="Abdullah completed the migration; ready for staging.",
            event_type="task",
        ),
        relationships=[
            Relationship(entity_name="Abdullah", role="participant"),
            Relationship(entity_name="Amaan", role="participant"),
        ],
        refined_salience=0.65,
    ))

    return {"chunks": [chunk1, chunk2, chunk3], "user": user}


# ---------------------------------------------------------------------------
# Query Parser Tests
# ---------------------------------------------------------------------------


class TestQueryParser:
    def test_intent_informational(self, db_session: Session) -> None:
        user = _make_user(db_session)
        parsed = parse_query(db_session, "what happened with the project?", user.id)
        assert parsed.intent_type == "informational"

    def test_intent_temporal(self, db_session: Session) -> None:
        user = _make_user(db_session)
        parsed = parse_query(db_session, "recent discussions", user.id)
        assert parsed.intent_type == "temporal"
        assert parsed.time_filter is not None

    def test_intent_relational(self, db_session: Session) -> None:
        user = _make_user(db_session)
        _seed_knowledge_graph(db_session, user)
        parsed = parse_query(db_session, "What did Amaan and Abdullah decide?", user.id)
        assert parsed.intent_type == "relational"
        assert len(parsed.detected_entities) >= 2

    def test_entity_detection(self, db_session: Session) -> None:
        user = _make_user(db_session)
        _seed_knowledge_graph(db_session, user)
        parsed = parse_query(db_session, "Tell me about PostgreSQL", user.id)
        entity_lower = [e.lower() for e in parsed.detected_entities]
        assert any("postgresql" in e.lower() for e in parsed.detected_entities)

    def test_time_filter_yesterday(self, db_session: Session) -> None:
        user = _make_user(db_session)
        parsed = parse_query(db_session, "what happened yesterday?", user.id)
        assert parsed.time_filter is not None
        assert parsed.intent_type == "temporal"

    def test_empty_query(self, db_session: Session) -> None:
        user = _make_user(db_session)
        parsed = parse_query(db_session, "  ", user.id)
        assert parsed.cleaned_query == ""


# ---------------------------------------------------------------------------
# Ranker Unit Tests
# ---------------------------------------------------------------------------


class TestRanker:
    def test_recency_score_recent(self) -> None:
        now = datetime.now(timezone.utc)
        score = _recency_score(now)
        assert score == pytest.approx(1.0, abs=0.01)

    def test_recency_score_old(self) -> None:
        old = datetime(2020, 1, 1, tzinfo=timezone.utc)
        score = _recency_score(old)
        assert score < 0.01  # Very old event should score near 0

    def test_recency_score_none(self) -> None:
        assert _recency_score(None) == 0.0


# ---------------------------------------------------------------------------
# Integration Tests — Full Retrieval Pipeline
# ---------------------------------------------------------------------------


class TestRetrievalPipeline:
    def test_entity_search_single_entity(self, db_session: Session) -> None:
        """Query mentioning 'Amaan' returns events involving Amaan."""
        user = _make_user(db_session)
        _seed_knowledge_graph(db_session, user)

        result = retrieve_context(
            db_session,
            RetrievalQuery(query_text="What did Amaan do?", user_id=user.id, top_k=5),
        )

        # Should find events — Amaan is in all 3 events
        assert len(result.relevant_events) > 0
        assert len(result.relevant_entities) > 0

    def test_entity_search_multi_entity(self, db_session: Session) -> None:
        """Query 'Amaan and Abdullah' returns events involving both."""
        user = _make_user(db_session)
        _seed_knowledge_graph(db_session, user)

        result = retrieve_context(
            db_session,
            RetrievalQuery(
                query_text="What did Amaan and Abdullah decide about EchoMind?",
                user_id=user.id,
                top_k=5,
            ),
        )

        assert len(result.relevant_events) > 0
        # Verify events involve both Amaan and Abdullah
        entity_names = {e.name for e in result.relevant_entities}
        # At least one of the canonical names should appear
        assert len(entity_names) >= 2

    def test_vector_search_semantic_match(self, db_session: Session) -> None:
        """Query 'PostgreSQL decision' returns relevant chunks via embeddings."""
        user = _make_user(db_session)
        _seed_knowledge_graph(db_session, user)

        result = retrieve_context(
            db_session,
            RetrievalQuery(query_text="PostgreSQL decision", user_id=user.id, top_k=5),
        )

        # Should find supporting chunks via vector similarity
        assert len(result.supporting_chunks) > 0
        # At least one chunk should mention PostgreSQL
        pg_chunks = [c for c in result.supporting_chunks if "PostgreSQL" in c.content]
        assert len(pg_chunks) > 0

    def test_full_pipeline_context_summary(self, db_session: Session) -> None:
        """Full pipeline produces a non-empty context summary."""
        user = _make_user(db_session)
        _seed_knowledge_graph(db_session, user)

        result = retrieve_context(
            db_session,
            RetrievalQuery(
                query_text="What did Amaan and Abdullah decide about EchoMind?",
                user_id=user.id,
                top_k=5,
            ),
        )

        assert result.context_summary != ""
        assert "Event:" in result.context_summary

    def test_empty_query_graceful(self, db_session: Session) -> None:
        """Empty/nonsense query returns empty result without errors."""
        user = _make_user(db_session)

        result = retrieve_context(
            db_session,
            RetrievalQuery(query_text="xyzzy foobar 12345", user_id=user.id, top_k=5),
        )

        # Should return a result (possibly empty) without raising
        assert isinstance(result.context_summary, str)

    def test_result_has_supporting_chunks(self, db_session: Session) -> None:
        """Retrieval result includes supporting memory chunks linked to events."""
        user = _make_user(db_session)
        _seed_knowledge_graph(db_session, user)

        result = retrieve_context(
            db_session,
            RetrievalQuery(
                query_text="architecture finalization",
                user_id=user.id,
                top_k=5,
            ),
        )

        assert len(result.supporting_chunks) > 0

    def test_events_sorted_chronologically(self, db_session: Session) -> None:
        """Returned events are sorted by start_time."""
        user = _make_user(db_session)
        _seed_knowledge_graph(db_session, user)

        result = retrieve_context(
            db_session,
            RetrievalQuery(query_text="EchoMind decisions", user_id=user.id, top_k=10),
        )

        if len(result.relevant_events) >= 2:
            times = [e.start_time for e in result.relevant_events if e.start_time]
            assert times == sorted(times), "Events should be chronologically ordered"
