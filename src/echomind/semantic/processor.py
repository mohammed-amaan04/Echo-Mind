from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from echomind.core.config import get_settings
from echomind.db.models.entity import Entity, TrackedEntity
from echomind.db.models.memory import MemoryChunk
from echomind.persistence.schemas import (
    EventCandidate,
    ExtractedEntity,
    Relationship,
    SemanticOutput,
)

logger = structlog.get_logger(__name__)

VALID_ENTITY_TYPES = frozenset(
    {
        "person",
        "project",
        "organization",
        "tool",
        "technology",
        "topic",
        "task",
    }
)
VALID_ROLES = frozenset({"participant", "subject", "organizer", "mentioned", "owner"})
VALID_EVENT_TYPES = frozenset({"decision", "meeting", "task", "discussion", "milestone", "other"})

_LLM_SALIENCE_WEIGHT = 0.40
_MAX_TRACKED_BOOST = 0.30
_MAX_PARTICIPANT_BOOST = 0.15
_RECENCY_BOOST = 0.05
_MAX_EVENT_TITLE_LENGTH = 80
_MAX_SUMMARY_LENGTH = 240

_ENTITY_SYSTEM_PROMPT = """You are an entity extraction assistant for a knowledge-graph pipeline.

Given a text message and a list of participant names, extract entities and return ONLY a JSON array.

Each element must contain exactly:
- name
- normalized_name
- entity_type (person|project|organization|tool|technology|topic|task)
- role_in_event (participant|subject|organizer|mentioned|owner)

Return ONLY raw JSON. No markdown fences, no explanation."""

_SALIENCE_SYSTEM_PROMPT = """You are a salience scoring assistant.
Given a message, return ONLY JSON:
{"salience": <float between 0.0 and 1.0>}
"""

_ENRICH_SYSTEM_PROMPT = """You are a knowledge-graph assistant.
Given a message and entities list, return ONLY a JSON object with exactly these keys:
{
  "relationships": [{"subject": "", "predicate": "", "object": ""}],
  "event_candidates": [""],
  "event_type": "decision|meeting|task|discussion|milestone|other",
  "summary": "one sentence"
}
"""


@dataclass
class SemanticEntity:
    name: str
    normalized_name: str
    entity_type: str
    role_in_event: str


def _clean_llm_json(raw: str) -> str:
    cleaned = re.sub(r"```(?:json)?", "", raw, flags=re.IGNORECASE).strip(" `\n\t")
    return cleaned


def _env_to_bool(env_var_name: str, default: bool) -> bool:
    parsed = str(os.getenv(env_var_name, str(default))).lower()
    if parsed in {"1", "true", "yes"}:
        return True
    if parsed in {"0", "false", "no"}:
        return False
    return default


def _normalize_text(value: str) -> str:
    value = re.sub(r"[^\w\s]", "", value.lower().strip())
    return re.sub(r"\s+", " ", value).strip()


def _parse_participants(participants: Any) -> list[str]:
    if participants is None:
        return []
    if isinstance(participants, list):
        return [str(p).strip() for p in participants if str(p).strip()]
    if isinstance(participants, dict):
        values: list[str] = []
        for key in ("participants", "names", "members", "people"):
            entry = participants.get(key)
            if isinstance(entry, list):
                values.extend(str(v).strip() for v in entry if str(v).strip())
            elif isinstance(entry, str) and entry.strip():
                values.append(entry.strip())
        if values:
            return values
        return [str(v).strip() for v in participants.values() if isinstance(v, str) and v.strip()]
    if isinstance(participants, str):
        return [participants.strip()] if participants.strip() else []
    return []


class OllamaSemanticProcessor:
    def __init__(self, model: str = "mistral") -> None:
        self.model = model
        try:
            import ollama

            ollama.chat(model=self.model, messages=[{"role": "user", "content": "ping"}])
            self._client = ollama
        except Exception as exc:
            raise RuntimeError(f"Ollama unavailable for model '{self.model}': {exc}") from exc

    def process(self, session: DbSession, chunk: MemoryChunk) -> SemanticOutput:
        entities = self._extract_entities(chunk)
        refined_salience = self._compute_salience(session, chunk, entities)
        enrich = self._enrich(chunk, entities)

        event_candidate: EventCandidate | None = None
        summary = enrich.get("summary", "").strip()
        event_candidates = enrich.get("event_candidates") or []
        event_type = enrich.get("event_type", "discussion")
        if event_type not in VALID_EVENT_TYPES:
            event_type = "discussion"

        if summary:
            first_candidate = next(iter(event_candidates), "")
            title = (first_candidate or summary[:_MAX_EVENT_TITLE_LENGTH]).strip()
            if title:
                event_candidate = EventCandidate(title=title, summary=summary, event_type=event_type)

        relationships = [Relationship(entity_name=e.name, role=e.role_in_event) for e in entities]

        return SemanticOutput(
            memory_chunk_id=chunk.id,
            entities=[ExtractedEntity(name=e.name, entity_type=e.entity_type) for e in entities],
            event_candidate=event_candidate,
            relationships=relationships,
            refined_salience=refined_salience,
        )

    def _extract_entities(self, chunk: MemoryChunk) -> list[SemanticEntity]:
        participants = _parse_participants(chunk.participants)
        payload = f"Participants: {json.dumps(participants)}\n\nMessage:\n{chunk.content}"
        response = self._client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": _ENTITY_SYSTEM_PROMPT},
                {"role": "user", "content": payload},
            ],
        )
        raw = _clean_llm_json(response["message"]["content"])
        items = json.loads(raw)
        if not isinstance(items, list):
            raise ValueError("Entity extractor response must be a JSON array")

        entities: list[SemanticEntity] = []
        for item in items:
            entity = self._parse_entity(item)
            if entity is not None:
                entities.append(entity)

        if not entities:
            logger.warning("phase2_no_entities_extracted", chunk_id=chunk.id)

        return self._deduplicate(entities)

    @staticmethod
    def _parse_entity(item: Any) -> SemanticEntity | None:
        if not isinstance(item, dict):
            return None
        name = str(item.get("name", "")).strip()
        normalized = str(item.get("normalized_name", "")).strip()
        entity_type = str(item.get("entity_type", "topic")).strip().lower() or "topic"
        role = str(item.get("role_in_event", "mentioned")).strip().lower() or "mentioned"

        if entity_type not in VALID_ENTITY_TYPES:
            entity_type = "topic"
        if role not in VALID_ROLES:
            role = "mentioned"

        normalized = _normalize_text(normalized or name)
        if not name or not normalized:
            return None

        return SemanticEntity(
            name=name,
            normalized_name=normalized,
            entity_type=entity_type,
            role_in_event=role,
        )

    @staticmethod
    def _deduplicate(entities: list[SemanticEntity]) -> list[SemanticEntity]:
        seen: set[tuple[str, str]] = set()
        deduped: list[SemanticEntity] = []
        for entity in entities:
            key = (entity.normalized_name, entity.entity_type)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(entity)
        return deduped

    def _compute_salience(
        self,
        session: DbSession,
        chunk: MemoryChunk,
        entities: list[SemanticEntity],
    ) -> float:
        score = float(chunk.initial_salience or 0.0)

        llm_score = self._llm_salience(chunk)
        score += llm_score * _LLM_SALIENCE_WEIGHT

        score += self._tracked_entity_boost(session, chunk.user_id, entities)
        score += _participant_boost(_parse_participants(chunk.participants))
        score += _recency_boost(chunk.timestamp)

        return max(0.0, min(round(score, 4), 1.0))

    def _llm_salience(self, chunk: MemoryChunk) -> float:
        try:
            response = self._client.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": _SALIENCE_SYSTEM_PROMPT},
                    {"role": "user", "content": chunk.content},
                ],
            )
            raw = _clean_llm_json(response["message"]["content"])
            data = json.loads(raw)
            return max(0.0, min(1.0, float(data.get("salience", 0.0))))
        except Exception as exc:
            logger.warning("phase2_llm_salience_failed", chunk_id=chunk.id, error=str(exc))
            return 0.0

    def _tracked_entity_boost(
        self,
        session: DbSession,
        user_id: int,
        entities: list[SemanticEntity],
    ) -> float:
        stmt = (
            select(Entity.normalized_name)
            .join(TrackedEntity, TrackedEntity.entity_id == Entity.id)
            .where(TrackedEntity.user_id == user_id)
        )
        tracked = {row[0] for row in session.execute(stmt).all()}
        if not tracked:
            return 0.0

        matched = {entity.normalized_name for entity in entities if entity.normalized_name in tracked}
        return min(0.1 * len(matched), _MAX_TRACKED_BOOST)

    def _enrich(self, chunk: MemoryChunk, entities: list[SemanticEntity]) -> dict[str, Any]:
        entity_names = [entity.name for entity in entities]
        payload = f"Entities: {json.dumps(entity_names)}\n\nMessage:\n{chunk.content}"

        response = self._client.chat(
            model=self.model,
            messages=[
                {"role": "system", "content": _ENRICH_SYSTEM_PROMPT},
                {"role": "user", "content": payload},
            ],
        )
        raw = _clean_llm_json(response["message"]["content"])
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Enrichment response must be a JSON object")
        return data


class FallbackSemanticProcessor:
    TOOL_KEYWORDS = {
        "postgresql",
        "mongodb",
        "redis",
        "docker",
        "kubernetes",
        "pgvector",
        "fastapi",
        "sqlalchemy",
        "ollama",
    }

    PROJECT_PATTERNS = [re.compile(r"\becho\s*-?\s*mind\b", re.IGNORECASE)]

    def process(self, _session: DbSession, chunk: MemoryChunk) -> SemanticOutput:
        participants = _parse_participants(chunk.participants)
        entities: list[SemanticEntity] = []
        seen_people: set[str] = set()
        for name in participants:
            normalized = _normalize_text(name)
            if not normalized or normalized in seen_people:
                continue
            seen_people.add(normalized)
            entities.append(
                SemanticEntity(
                    name=name,
                    normalized_name=normalized,
                    entity_type="person",
                    role_in_event="participant",
                )
            )

        lower_content = chunk.content.lower()
        for token in self.TOOL_KEYWORDS:
            if re.search(rf"\b{re.escape(token)}\b", lower_content):
                entities.append(
                    SemanticEntity(
                        name=token,
                        normalized_name=token,
                        entity_type="tool",
                        role_in_event="mentioned",
                    )
                )

        for pattern in self.PROJECT_PATTERNS:
            if pattern.search(chunk.content):
                entities.append(
                    SemanticEntity(
                        name="EchoMind",
                        normalized_name="echomind",
                        entity_type="project",
                        role_in_event="subject",
                    )
                )

        entities = OllamaSemanticProcessor._deduplicate(entities)

        refined_salience = _fallback_salience(chunk, participants)
        summary = _fallback_summary(chunk.content)
        event_candidate: EventCandidate | None = None
        if summary:
            title = summary[:_MAX_EVENT_TITLE_LENGTH].rstrip()
            if title:
                event_candidate = EventCandidate(title=title, summary=summary, event_type="discussion")

        return SemanticOutput(
            memory_chunk_id=chunk.id,
            entities=[ExtractedEntity(name=e.name, entity_type=e.entity_type) for e in entities],
            event_candidate=event_candidate,
            relationships=[Relationship(entity_name=e.name, role=e.role_in_event) for e in entities],
            refined_salience=refined_salience,
        )


class Phase2SemanticPipeline:
    def __init__(self, model: str = "mistral") -> None:
        settings = get_settings()
        self.model = model or settings.ollama_model

        fallback_enabled = _env_to_bool("ECHOMIND_PHASE2_FALLBACK", settings.echomind_phase2_fallback)
        ollama_required = _env_to_bool("ECHOMIND_OLLAMA_REQUIRED", settings.echomind_ollama_required)

        try:
            self._processor: OllamaSemanticProcessor | FallbackSemanticProcessor = (
                OllamaSemanticProcessor(model=self.model)
            )
            logger.info("phase2_ollama_enabled", model=self.model)
        except Exception as exc:
            if ollama_required or not fallback_enabled:
                raise
            logger.warning(
                "phase2_ollama_unavailable_using_fallback",
                model=self.model,
                error=str(exc),
                fallback_enabled=fallback_enabled,
            )
            self._processor = FallbackSemanticProcessor()

    def process(self, session: DbSession, chunk: MemoryChunk) -> SemanticOutput:
        return self._processor.process(session, chunk)


def _participant_boost(participants: list[str]) -> float:
    size = len(participants)
    if size >= 3:
        return _MAX_PARTICIPANT_BOOST
    if size == 2:
        return _MAX_PARTICIPANT_BOOST * 0.5
    return 0.0


def _recency_boost(timestamp: datetime) -> float:
    now = datetime.now(tz=UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    age_hours = (now - timestamp).total_seconds() / 3600
    return _RECENCY_BOOST if age_hours <= 24 else 0.0


def _fallback_salience(chunk: MemoryChunk, participants: list[str]) -> float:
    base = float(chunk.initial_salience or 0.0)
    score = base + _participant_boost(participants) + _recency_boost(chunk.timestamp)
    return max(0.0, min(round(score, 4), 1.0))


def _fallback_summary(content: str) -> str:
    clean = " ".join(content.split())
    if not clean:
        return ""
    sentence = re.split(r"(?<=[.!?])\s+", clean)[0]
    return sentence[:_MAX_SUMMARY_LENGTH]
