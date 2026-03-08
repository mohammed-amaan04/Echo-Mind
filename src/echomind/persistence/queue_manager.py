"""Queue state manager — tracks processing_queue status transitions."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from echomind.db.models.pipeline import ProcessingQueueEntry
from echomind.persistence.logging_service import log_info


def mark_processing(session: DbSession, memory_chunk_id: int) -> ProcessingQueueEntry | None:
    """Transition queue entry to *processing*.  Returns the entry or None."""
    stmt = select(ProcessingQueueEntry).where(
        ProcessingQueueEntry.memory_chunk_id == memory_chunk_id,
    )
    entry = session.execute(stmt).scalar_one_or_none()
    if entry is None:
        return None
    entry.status = "processing"
    session.flush()
    log_info(session, "queue_manager", f"Queue entry for chunk {memory_chunk_id} → processing")
    return entry


def mark_done(session: DbSession, memory_chunk_id: int) -> None:
    """Transition queue entry to *done*."""
    stmt = select(ProcessingQueueEntry).where(
        ProcessingQueueEntry.memory_chunk_id == memory_chunk_id,
    )
    entry = session.execute(stmt).scalar_one_or_none()
    if entry is not None:
        entry.status = "done"
        session.flush()
        log_info(session, "queue_manager", f"Queue entry for chunk {memory_chunk_id} → done")


def mark_failed(session: DbSession, memory_chunk_id: int) -> int:
    """Transition queue entry to *failed*, increment retry_count.

    Returns the new retry count (0 if entry was not found).
    """
    stmt = select(ProcessingQueueEntry).where(
        ProcessingQueueEntry.memory_chunk_id == memory_chunk_id,
    )
    entry = session.execute(stmt).scalar_one_or_none()
    if entry is not None:
        entry.status = "failed"
        entry.retry_count += 1
        session.flush()
        return entry.retry_count
    return 0
