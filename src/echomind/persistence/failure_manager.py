"""Failure recovery manager — escalate unrecoverable jobs to failed_jobs."""

from __future__ import annotations

from sqlalchemy.orm import Session as DbSession

from echomind.db.models.pipeline import FailedJob
from echomind.persistence.logging_service import log_error

MAX_RETRIES = 3


def escalate_if_needed(
    session: DbSession,
    memory_chunk_id: int,
    retry_count: int,
    failure_reason: str,
    stage: str,
) -> bool:
    """Move to *failed_jobs* when retry limit is exceeded.

    Returns ``True`` if the job was escalated.
    """
    if retry_count <= MAX_RETRIES:
        return False

    failed = FailedJob(
        memory_chunk_id=memory_chunk_id,
        failure_reason=failure_reason,
        stage=stage,
        reference_ids={"memory_chunk_id": memory_chunk_id},
    )
    session.add(failed)
    session.flush()
    log_error(
        session,
        "failure_manager",
        f"Escalated chunk {memory_chunk_id} to failed_jobs after {retry_count} retries",
        {"memory_chunk_id": memory_chunk_id, "stage": stage},
    )
    return True
