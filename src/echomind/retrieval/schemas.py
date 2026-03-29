"""Data contracts for the retrieval layer.

These dataclasses define the input/output interface for Phase 4 retrieval.
The retrieval engine receives a ``RetrievalQuery`` and returns a
``RetrievalResult`` ready for consumption by Phase 5 (Response Layer).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from echomind.db.models.entity import Entity
from echomind.db.models.event import Event
from echomind.db.models.memory import MemoryChunk


@dataclass
class RetrievalQuery:
    """Input to the retrieval engine."""

    query_text: str
    user_id: int
    top_k: int = 10


@dataclass
class TimeRange:
    """An optional time window for filtering results."""

    start: datetime
    end: datetime


@dataclass
class ParsedQuery:
    """Structured representation of a parsed user query."""

    cleaned_query: str
    detected_entities: list[str] = field(default_factory=list)
    intent_type: str = "informational"  # informational | temporal | relational
    time_filter: TimeRange | None = None


@dataclass
class ScoredEvent:
    """An event with a composite relevance score."""

    event: Event
    score: float = 0.0
    vector_similarity: float = 0.0
    entity_overlap: float = 0.0
    recency_score: float = 0.0


@dataclass
class ScoredChunk:
    """A memory chunk with its vector similarity score."""

    chunk: MemoryChunk
    similarity: float = 0.0


@dataclass
class RetrievalResult:
    """Output of the retrieval engine — ready for Phase 5 consumption."""

    relevant_events: list[Event] = field(default_factory=list)
    relevant_entities: list[Entity] = field(default_factory=list)
    supporting_chunks: list[MemoryChunk] = field(default_factory=list)
    context_summary: str = ""
