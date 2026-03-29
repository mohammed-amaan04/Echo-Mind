"""Phase 5 response layer tests.

Tests mock the OpenAI client to avoid real API calls.
Confidence scoring, action suggestions, and context formatting
don't need mocking — they are pure logic.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from echomind.db.models.entity import Entity
from echomind.db.models.event import Event
from echomind.db.models.memory import MemoryChunk
from echomind.response.actions import suggest_actions
from echomind.response.confidence import compute_confidence
from echomind.response.context_formatter import format_context
from echomind.response.engine import generate_response
from echomind.response.prompt_builder import SYSTEM_PROMPT, build_messages
from echomind.response.schemas import ResponseRequest
from echomind.retrieval.schemas import RetrievalResult


# ---------------------------------------------------------------------------
# Helpers — create fake DB model objects (no DB needed)
# ---------------------------------------------------------------------------


def _fake_event(
    id: int = 1,
    title: str = "Test Event",
    event_type: str = "decision",
    summary: str = "Test summary",
    salience: float = 0.7,
    start_time: datetime | None = None,
) -> MagicMock:
    """Create a fake Event-like object without DB."""
    ev = MagicMock(spec=Event)
    ev.id = id
    ev.title = title
    ev.event_type = event_type
    ev.summary = summary
    ev.salience_score = salience
    ev.start_time = start_time or datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    ev.created_at = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    ev.created_from_chunk_id = None
    ev.user_id = 1
    return ev


def _fake_entity(
    id: int = 1,
    name: str = "Amaan",
    entity_type: str = "person",
    mentions: int = 3,
    salience: float = 0.6,
) -> MagicMock:
    ent = MagicMock(spec=Entity)
    ent.id = id
    ent.name = name
    ent.entity_type = entity_type
    ent.mention_count = mentions
    ent.salience_score = salience
    ent.normalized_name = name.lower()
    ent.user_id = 1
    return ent


def _fake_chunk(
    id: int = 1,
    content: str = "Test conversation content",
    source_type: str = "whatsapp",
    ts: datetime | None = None,
) -> MagicMock:
    chunk = MagicMock(spec=MemoryChunk)
    chunk.id = id
    chunk.content = content
    chunk.source_type = source_type
    chunk.timestamp = ts or datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
    chunk.user_id = 1
    return chunk


def _make_retrieval_result(
    events: list[Event] | None = None,
    entities: list[Entity] | None = None,
    chunks: list[MemoryChunk] | None = None,
    summary: str = "",
) -> RetrievalResult:
    return RetrievalResult(
        relevant_events=events or [],
        relevant_entities=entities or [],
        supporting_chunks=chunks or [],
        context_summary=summary,
    )


# ---------------------------------------------------------------------------
# Context Formatter Tests
# ---------------------------------------------------------------------------


class TestContextFormatter:
    def test_events_formatted_chronologically(self) -> None:
        ev1 = _fake_event(id=1, title="Later", start_time=datetime(2026, 3, 5, tzinfo=timezone.utc))
        ev2 = _fake_event(id=2, title="Earlier", start_time=datetime(2026, 3, 1, tzinfo=timezone.utc))

        formatted = format_context([ev1, ev2], [], [])
        # Earlier should come before Later
        pos_earlier = formatted.events_text.find("Earlier")
        pos_later = formatted.events_text.find("Later")
        assert pos_earlier < pos_later

    def test_chunks_truncated(self) -> None:
        long_content = "A" * 500
        chunk = _fake_chunk(id=1, content=long_content)

        formatted = format_context([], [], [chunk])
        assert len(formatted.chunks_text) < 500
        assert "…" in formatted.chunks_text

    def test_empty_context(self) -> None:
        formatted = format_context([], [], [])
        assert "No relevant events" in formatted.events_text
        assert "No supporting evidence" in formatted.chunks_text

    def test_entity_list(self) -> None:
        entities = [
            _fake_entity(id=1, name="Amaan", entity_type="person"),
            _fake_entity(id=2, name="EchoMind", entity_type="project"),
        ]
        formatted = format_context([], entities, [])
        assert "Amaan (person)" in formatted.entity_list
        assert "EchoMind (project)" in formatted.entity_list


# ---------------------------------------------------------------------------
# Prompt Builder Tests
# ---------------------------------------------------------------------------


class TestPromptBuilder:
    def test_message_structure(self) -> None:
        from echomind.response.context_formatter import FormattedContext

        ctx = FormattedContext(
            events_text="[decision] DB chosen",
            chunks_text="[1] (whatsapp) Some evidence",
            entity_list="Amaan (person)",
        )
        messages = build_messages("What happened?", ctx)

        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "What happened?" in messages[1]["content"]
        assert "DB chosen" in messages[1]["content"]

    def test_system_prompt_has_grounding_rules(self) -> None:
        assert "ONLY using the provided context" in SYSTEM_PROMPT
        assert "DO NOT" in SYSTEM_PROMPT


# ---------------------------------------------------------------------------
# Confidence Scoring Tests
# ---------------------------------------------------------------------------


class TestConfidence:
    def test_high_confidence(self) -> None:
        """Rich context → high confidence."""
        result = _make_retrieval_result(
            events=[
                _fake_event(id=1, salience=0.8),
                _fake_event(id=2, salience=0.9),
                _fake_event(id=3, salience=0.7),
            ],
            entities=[
                _fake_entity(id=1, name="Amaan"),
                _fake_entity(id=2, name="Abdullah"),
            ],
        )
        score = compute_confidence(result, query_entity_names=["Amaan", "Abdullah"])
        assert score > 0.6

    def test_low_confidence(self) -> None:
        """No context → low confidence."""
        result = _make_retrieval_result()
        score = compute_confidence(result)
        assert score == 0.0

    def test_partial_confidence(self) -> None:
        """Some context → moderate confidence."""
        result = _make_retrieval_result(
            events=[_fake_event(id=1, salience=0.5)],
        )
        score = compute_confidence(result, query_entity_names=["Amaan"])
        assert 0.0 < score < 0.8


# ---------------------------------------------------------------------------
# Action Suggestion Tests
# ---------------------------------------------------------------------------


class TestActions:
    def test_task_event_suggests_reminder(self) -> None:
        events = [_fake_event(id=1, event_type="task", title="Finish migration")]
        actions = suggest_actions(events, [])
        assert len(actions) >= 1
        assert actions[0].action_type == "set_reminder"
        assert "migration" in actions[0].description.lower()

    def test_decision_event_suggests_draft(self) -> None:
        events = [_fake_event(id=1, event_type="decision", title="Use PostgreSQL")]
        actions = suggest_actions(events, [])
        assert len(actions) >= 1
        assert actions[0].action_type == "draft_message"

    def test_gmail_chunk_suggests_reply(self) -> None:
        chunks = [_fake_chunk(id=1, source_type="gmail")]
        actions = suggest_actions([], chunks)
        assert len(actions) >= 1
        assert actions[0].action_type == "draft_reply"

    def test_max_suggestions_capped(self) -> None:
        events = [
            _fake_event(id=1, event_type="task"),
            _fake_event(id=2, event_type="decision"),
            _fake_event(id=3, event_type="meeting"),
        ]
        chunks = [_fake_chunk(id=1, source_type="gmail")]
        actions = suggest_actions(events, chunks, max_suggestions=2)
        assert len(actions) <= 2

    def test_no_actions_for_empty_input(self) -> None:
        actions = suggest_actions([], [])
        assert actions == []


# ---------------------------------------------------------------------------
# Engine (Orchestrator) Tests — LLM mocked
# ---------------------------------------------------------------------------


class TestEngine:
    @patch("echomind.response.engine.call_llm")
    def test_contextual_answer(self, mock_llm: MagicMock) -> None:
        """Full pipeline returns a structured response with mocked LLM."""
        mock_llm.return_value = "Based on the context, Amaan and Abdullah decided to use PostgreSQL."

        result = _make_retrieval_result(
            events=[
                _fake_event(id=1, event_type="decision", title="PostgreSQL chosen", salience=0.8),
            ],
            entities=[
                _fake_entity(id=1, name="Amaan"),
                _fake_entity(id=2, name="Abdullah"),
            ],
            chunks=[
                _fake_chunk(id=1, content="Amaan: Let's use PostgreSQL"),
            ],
            summary="Team chose PostgreSQL.",
        )
        request = ResponseRequest(
            query_text="What did Amaan and Abdullah decide?",
            retrieval_result=result,
            user_id=1,
        )
        output = generate_response(request)

        assert "PostgreSQL" in output.answer
        assert output.confidence_score > 0.0
        assert 1 in output.supporting_events
        mock_llm.assert_called_once()

    @patch("echomind.response.engine.call_llm")
    def test_empty_context_no_llm_call(self, mock_llm: MagicMock) -> None:
        """Empty context returns 'no info' without calling LLM."""
        result = _make_retrieval_result()
        request = ResponseRequest(
            query_text="What did Elon Musk tell me?",
            retrieval_result=result,
            user_id=1,
        )
        output = generate_response(request)

        assert "don't have enough information" in output.answer.lower()
        assert output.confidence_score == 0.0
        assert output.suggested_actions == []
        mock_llm.assert_not_called()

    @patch("echomind.response.engine.call_llm")
    def test_actions_included_in_output(self, mock_llm: MagicMock) -> None:
        """Pipeline includes action suggestions in the output."""
        mock_llm.return_value = "The migration is ready for staging."

        result = _make_retrieval_result(
            events=[
                _fake_event(id=1, event_type="task", title="Schema migration"),
            ],
            chunks=[
                _fake_chunk(id=1, content="Migration is complete"),
            ],
        )
        request = ResponseRequest(
            query_text="What about the migration?",
            retrieval_result=result,
            user_id=1,
        )
        output = generate_response(request)

        assert len(output.suggested_actions) >= 1
        assert output.suggested_actions[0].action_type == "set_reminder"
