from __future__ import annotations

from datetime import UTC, datetime

from echomind.db.models.memory import MemoryChunk
from echomind.semantic.processor import (
    OllamaSemanticProcessor,
    Phase2SemanticPipeline,
    SemanticEntity,
    _clean_llm_json,
)


def _chunk(content: str = "Amaan and Abdullah discussed EchoMind with PostgreSQL") -> MemoryChunk:
    return MemoryChunk(
        id=1,
        user_id=1,
        source_type="whatsapp",
        content=content,
        timestamp=datetime(2026, 3, 1, 10, 0, tzinfo=UTC),
        participants=["Amaan", "Abdullah"],
        initial_salience=0.4,
        is_processed=False,
    )


def test_clean_llm_json_strips_markdown_fences() -> None:
    raw = '```json\n[{"name":"EchoMind"}]\n```'
    assert _clean_llm_json(raw) == '[{"name":"EchoMind"}]'


def test_entity_parse_clamps_type_and_role_and_deduplicates() -> None:
    parsed = OllamaSemanticProcessor._parse_entity(
        {
            "name": "EchoMind",
            "normalized_name": "EchoMind",
            "entity_type": "invalid",
            "role_in_event": "invalid",
        }
    )
    assert parsed is not None
    assert parsed.entity_type == "topic"
    assert parsed.role_in_event == "mentioned"

    deduped = OllamaSemanticProcessor._deduplicate(
        [
            SemanticEntity("EchoMind", "echomind", "project", "subject"),
            SemanticEntity("EchoMind", "echomind", "project", "subject"),
        ]
    )
    assert len(deduped) == 1


def test_pipeline_falls_back_when_ollama_unavailable(monkeypatch) -> None:
    class BrokenOllama:
        @staticmethod
        def chat(*_args, **_kwargs):
            raise RuntimeError("unavailable")

    monkeypatch.setitem(__import__("sys").modules, "ollama", BrokenOllama)
    monkeypatch.setenv("ECHOMIND_PHASE2_FALLBACK", "1")
    monkeypatch.setenv("ECHOMIND_OLLAMA_REQUIRED", "false")

    pipeline = Phase2SemanticPipeline(model="mistral")
    out = pipeline.process(session=None, chunk=_chunk())

    names = {entity.name.lower() for entity in out.entities}
    assert "amaan" in names
    assert out.refined_salience >= 0.4
    roles = {rel.role for rel in out.relationships}
    assert "participant" in roles
