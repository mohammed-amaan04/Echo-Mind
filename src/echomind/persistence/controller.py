"""Phase 3 Persistence Controller — main orchestrator.

Takes a ``SemanticOutput`` from the semantic pipeline and persists all
extracted knowledge (entities, events, relationships) into the database
while maintaining queue state, traceability, and failure recovery.
"""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from echomind.db.models.memory import MemoryChunk
from echomind.persistence import (
    entity_service,
    event_service,
    failure_manager,
    logging_service,
    queue_manager,
    relationship_service,
)
from echomind.persistence.schemas import SemanticOutput

logger = structlog.get_logger(__name__)


def persist_semantic_output(session: DbSession, semantic_output: SemanticOutput) -> dict:
    """Persist a single ``SemanticOutput`` to the knowledge schema.

    Steps executed in order:
    1. Mark the processing-queue entry as *processing*.
    2. Retrieve the memory chunk and store the refined salience / processed flag.
    3. Normalize and upsert every extracted entity.
    4. Create an event if the salience threshold is met.
    5. Link entities to the event (knowledge-graph edges).
    6. Link the event back to the originating memory chunk (traceability).
    7. Mark the queue entry as *done*.

    On failure the queue entry is marked *failed*, retry_count is
    incremented, and the job is escalated to *failed_jobs* when the
    retry limit is exceeded.

    Returns a summary ``dict`` describing the outcome.
    """
    chunk_id = semantic_output.memory_chunk_id
    result: dict = {
        "memory_chunk_id": chunk_id,
        "entities_upserted": 0,
        "event_created": False,
        "links_created": 0,
        "status": "pending",
    }

    # Step 1 — mark queue entry as processing
    queue_manager.mark_processing(session, chunk_id)

    try:
        # Step 2 — retrieve and update memory chunk
        stmt = select(MemoryChunk).where(MemoryChunk.id == chunk_id)
        chunk = session.execute(stmt).scalar_one_or_none()
        if chunk is None:
            raise ValueError(f"Memory chunk {chunk_id} not found")

        chunk.refined_salience = semantic_output.refined_salience
        chunk.is_processed = True
        session.flush()

        user_id = chunk.user_id

        # Step 3 — upsert entities
        entity_map = entity_service.upsert_entities(
            session,
            user_id,
            semantic_output.entities,
            chunk.timestamp,
            semantic_output.refined_salience,
        )
        result["entities_upserted"] = len(entity_map)

        # Step 4 — create event if eligible
        event = event_service.create_event_if_eligible(
            session,
            user_id,
            chunk,
            semantic_output.event_candidate,
            semantic_output.refined_salience,
        )

        if event is not None:
            result["event_created"] = True

            # Step 5 — link entities → event
            links = relationship_service.link_entities_to_event(
                session, event, semantic_output.relationships, entity_map
            )
            result["links_created"] = len(links)

            # Step 6 — link event → memory chunk
            relationship_service.link_event_to_memory(session, event, chunk_id)

        # Step 7 — mark queue done
        queue_manager.mark_done(session, chunk_id)
        result["status"] = "done"

        session.commit()
        logger.info("persistence_complete", **result)

    except Exception as exc:
        session.rollback()
        error_msg = str(exc)
        logger.error("persistence_failed", memory_chunk_id=chunk_id, error=error_msg)

        # Record the failure in a fresh transaction
        try:
            retry_count = queue_manager.mark_failed(session, chunk_id)
            logging_service.log_error(
                session,
                "persistence_controller",
                f"Failed to persist chunk {chunk_id}: {error_msg}",
                {"memory_chunk_id": chunk_id, "stage": "persist_semantic_output"},
            )
            failure_manager.escalate_if_needed(
                session, chunk_id, retry_count, error_msg, "persist_semantic_output"
            )
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("failure_handling_failed", memory_chunk_id=chunk_id)

        result["status"] = "failed"
        result["error"] = error_msg

    return result
