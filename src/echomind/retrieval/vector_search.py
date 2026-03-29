"""Vector retrieval — pgvector semantic similarity search.

Embeds the user query using ``all-MiniLM-L6-v2`` (lazy-loaded singleton) and
performs cosine-distance search against ``memory_chunks.embedding``.
"""

from __future__ import annotations

import structlog
from sqlalchemy import text
from sqlalchemy.orm import Session as DbSession

from echomind.core.config import get_settings
from echomind.db.models.memory import MemoryChunk
from echomind.retrieval.schemas import ParsedQuery, ScoredChunk

logger = structlog.get_logger(__name__)

# ── Lazy-loaded embedding model (singleton) ─────────────────────────────────

_model = None


def _get_model():
    """Load the sentence-transformer model on first use."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        settings = get_settings()
        logger.info("loading_embedding_model", model=settings.embedding_model)
        _model = SentenceTransformer(settings.embedding_model)
    return _model


def embed_query(query_text: str) -> list[float]:
    """Convert query text to a 384-dimensional embedding vector."""
    model = _get_model()
    embedding = model.encode(query_text, normalize_embeddings=True)
    return embedding.tolist()


def vector_search(
    session: DbSession,
    parsed: ParsedQuery,
    user_id: int,
    top_k: int = 20,
) -> list[ScoredChunk]:
    """Find the most semantically similar memory chunks via pgvector.

    Uses cosine distance (``<=>``) and converts to similarity (``1 - distance``).
    Applies optional time filter from the parsed query.
    """
    query_embedding = embed_query(parsed.cleaned_query)

    # Build the SQL — pgvector cosine distance operator is <=>
    sql_parts = [
        "SELECT id, user_id, source_type, external_message_id, content,",
        "  timestamp, participants, embedding, initial_salience, refined_salience,",
        "  is_processed, session_id, created_at,",
        "  (embedding <=> CAST(:query_vec AS vector)) AS distance",
        "FROM memory_chunks",
        "WHERE user_id = :user_id",
        "  AND embedding IS NOT NULL",
    ]
    params: dict = {"user_id": user_id, "query_vec": str(query_embedding)}

    if parsed.time_filter is not None:
        sql_parts.append("  AND timestamp >= :time_start AND timestamp <= :time_end")
        params["time_start"] = parsed.time_filter.start
        params["time_end"] = parsed.time_filter.end

    sql_parts.append("ORDER BY distance ASC")
    sql_parts.append("LIMIT :top_k")
    params["top_k"] = top_k

    sql = text("\n".join(sql_parts))
    rows = session.execute(sql, params).fetchall()

    scored: list[ScoredChunk] = []
    for row in rows:
        chunk = session.get(MemoryChunk, row.id)
        if chunk is not None:
            similarity = max(0.0, 1.0 - row.distance)
            scored.append(ScoredChunk(chunk=chunk, similarity=similarity))

    logger.info("vector_search_complete", results=len(scored), top_k=top_k)
    return scored
