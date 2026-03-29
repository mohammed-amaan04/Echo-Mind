"""Seed Phase 4 — add real embeddings to existing memory chunks.

Loads the ``all-MiniLM-L6-v2`` model and generates embeddings for every
memory chunk that does not already have one.  This makes the Phase 3
seeded data queryable via vector search.

Run:
    python scripts/seed_phase4.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure src/ is importable when running as a script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sentence_transformers import SentenceTransformer  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from echomind.core.config import get_settings  # noqa: E402
from echomind.db.base import Base  # noqa: E402
from echomind.db.models import *  # noqa: E401,E402,F401,F403
from echomind.db.models.memory import MemoryChunk  # noqa: E402
from echomind.db.session import SessionLocal, engine  # noqa: E402


def seed_embeddings() -> None:
    """Generate and store embeddings for all memory chunks missing them."""
    settings = get_settings()
    print(f"[seed_phase4] Loading embedding model: {settings.embedding_model}")
    model = SentenceTransformer(settings.embedding_model)

    # Ensure tables exist
    Base.metadata.create_all(engine)

    session = SessionLocal()
    try:
        # Find chunks without embeddings
        stmt = select(MemoryChunk).where(MemoryChunk.embedding.is_(None))
        chunks = session.execute(stmt).scalars().all()

        if not chunks:
            print("[seed_phase4] All chunks already have embeddings. Nothing to do.")
            return

        print(f"[seed_phase4] Generating embeddings for {len(chunks)} chunks...")

        for i, chunk in enumerate(chunks):
            embedding = model.encode(chunk.content, normalize_embeddings=True).tolist()
            # Use raw SQL update to set the pgvector column
            session.execute(
                text(
                    "UPDATE memory_chunks SET embedding = CAST(:vec AS vector) WHERE id = :id"
                ),
                {"vec": str(embedding), "id": chunk.id},
            )
            print(f"  [{i + 1}/{len(chunks)}] Chunk {chunk.id}: embedded ({len(embedding)} dims)")

        session.commit()
        print(f"[seed_phase4] Done — {len(chunks)} embeddings stored.")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_embeddings()
