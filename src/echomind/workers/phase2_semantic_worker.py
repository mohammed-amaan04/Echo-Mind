from __future__ import annotations

import time

import structlog
from sqlalchemy import select

from echomind.db.models.memory import MemoryChunk
from echomind.db.models.pipeline import ProcessingQueueEntry
from echomind.db.session import SessionLocal
from echomind.persistence.controller import persist_semantic_output
from echomind.semantic import Phase2SemanticPipeline

logger = structlog.get_logger(__name__)


def _pending_chunks(session, limit: int) -> list[MemoryChunk]:
    stmt = (
        select(MemoryChunk)
        .join(ProcessingQueueEntry, ProcessingQueueEntry.memory_chunk_id == MemoryChunk.id)
        .where(ProcessingQueueEntry.status == "pending", MemoryChunk.is_processed.is_(False))
        .order_by(MemoryChunk.timestamp.asc())
        .limit(limit)
    )
    return list(session.execute(stmt).scalars().all())


def run_phase2_worker(
    model: str = "mistral",
    limit: int = 10,
    once: bool = False,
    poll_interval_seconds: int = 5,
) -> None:
    pipeline = Phase2SemanticPipeline(model=model)

    while True:
        processed = 0
        try:
            with SessionLocal() as session:
                chunks = _pending_chunks(session, limit)
                if not chunks:
                    logger.info("phase2_worker_no_pending_chunks")
                for chunk in chunks:
                    semantic_output = pipeline.process(session, chunk)
                    result = persist_semantic_output(session, semantic_output)
                    processed += 1
                    logger.info("phase2_chunk_processed", chunk_id=chunk.id, status=result.get("status"))
        except Exception as exc:
            logger.exception("phase2_worker_iteration_failed", error=str(exc))
            if once:
                raise

        if once:
            return
        if processed == 0:
            time.sleep(poll_interval_seconds)
