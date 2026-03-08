"""Data contracts for the persistence layer.

These dataclasses define the interface between the semantic pipeline (Phase 2)
and the persistence layer (Phase 3).  The semantic layer produces a
``SemanticOutput`` for each processed memory chunk and hands it to
``persist_semantic_output`` without writing to the database itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ExtractedEntity:
    """An entity detected by the semantic layer."""

    name: str
    entity_type: str  # "person", "project", "organization", "topic", …


@dataclass
class EventCandidate:
    """A meaningful event detected by the semantic layer."""

    title: str
    summary: str
    event_type: str  # "meeting", "decision", "discussion", "task", …


@dataclass
class Relationship:
    """A link between an entity and the event candidate."""

    entity_name: str
    role: str  # "participant", "subject", "mentioned", "organizer"


@dataclass
class SemanticOutput:
    """The complete output of the semantic layer for a single memory chunk.

    This is the sole input to the Phase 3 persistence controller.
    """

    memory_chunk_id: int
    entities: list[ExtractedEntity] = field(default_factory=list)
    event_candidate: EventCandidate | None = None
    relationships: list[Relationship] = field(default_factory=list)
    refined_salience: float = 0.0
