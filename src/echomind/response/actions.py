"""Action suggestion engine — suggest next steps based on context.

Rule-based (no LLM needed).  Examines event types and chunk sources
to propose useful follow-up actions.  NEVER auto-executes.
"""

from __future__ import annotations

from echomind.db.models.event import Event
from echomind.db.models.memory import MemoryChunk
from echomind.response.schemas import ActionSuggestion


def _suggest_from_events(events: list[Event]) -> list[ActionSuggestion]:
    """Generate action suggestions from event types."""
    suggestions: list[ActionSuggestion] = []
    seen_types: set[str] = set()

    for event in events:
        etype = event.event_type

        if etype == "task" and "task" not in seen_types:
            suggestions.append(ActionSuggestion(
                action_type="set_reminder",
                description=f"Set a reminder for: {event.title}",
                payload={
                    "event_id": event.id,
                    "title": event.title,
                    "due_date": event.start_time.isoformat() if event.start_time else None,
                },
            ))
            seen_types.add("task")

        elif etype == "decision" and "decision" not in seen_types:
            suggestions.append(ActionSuggestion(
                action_type="draft_message",
                description=f"Confirm decision: {event.title}",
                payload={
                    "event_id": event.id,
                    "subject": event.title,
                    "suggested_content": f"Following up on our decision: {event.summary or event.title}",
                },
            ))
            seen_types.add("decision")

        elif etype == "meeting" and "meeting" not in seen_types:
            suggestions.append(ActionSuggestion(
                action_type="follow_up",
                description=f"Follow up on meeting: {event.title}",
                payload={
                    "event_id": event.id,
                    "title": event.title,
                },
            ))
            seen_types.add("meeting")

    return suggestions


def _suggest_from_chunks(chunks: list[MemoryChunk]) -> list[ActionSuggestion]:
    """Generate action suggestions from source types."""
    suggestions: list[ActionSuggestion] = []
    seen_sources: set[str] = set()

    for chunk in chunks:
        source = chunk.source_type

        if source == "gmail" and "gmail" not in seen_sources:
            suggestions.append(ActionSuggestion(
                action_type="draft_reply",
                description="Draft a reply to the related email",
                payload={"source_type": "gmail", "chunk_id": chunk.id},
            ))
            seen_sources.add("gmail")

    return suggestions


def suggest_actions(
    events: list[Event],
    chunks: list[MemoryChunk],
    max_suggestions: int = 3,
) -> list[ActionSuggestion]:
    """Generate action suggestions from events and chunks.

    Returns at most ``max_suggestions`` suggestions, prioritizing
    event-based actions over source-based ones.
    """
    suggestions: list[ActionSuggestion] = []
    suggestions.extend(_suggest_from_events(events))
    suggestions.extend(_suggest_from_chunks(chunks))
    return suggestions[:max_suggestions]
