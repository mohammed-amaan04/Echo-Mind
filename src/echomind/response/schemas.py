"""Data contracts for the response layer.

These dataclasses define the input/output interface for Phase 5 response
generation.  The response engine receives a ``ResponseRequest`` and returns
a ``ResponseOutput`` ready for the UI layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from echomind.retrieval.schemas import RetrievalResult


@dataclass
class ResponseRequest:
    """Input to the response engine."""

    query_text: str
    retrieval_result: RetrievalResult
    user_id: int


@dataclass
class ActionSuggestion:
    """A suggested action the user may want to take — never auto-executed."""

    action_type: str          # set_reminder | draft_message | follow_up
    description: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResponseOutput:
    """Output of the response engine — ready for UI consumption."""

    answer: str
    supporting_events: list[int] = field(default_factory=list)
    supporting_entities: list[int] = field(default_factory=list)
    confidence_score: float = 0.0
    suggested_actions: list[ActionSuggestion] = field(default_factory=list)
