"""Demo script — run retrieval queries against the seeded knowledge graph.

Shows the full retrieval pipeline output for several example queries.
Requires: docker compose up, alembic upgrade head, seed_phase3.py, seed_phase4.py

Run:
    python scripts/demo_retrieval.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from echomind.db.session import SessionLocal
from echomind.retrieval import RetrievalQuery, retrieve_context

QUERIES = [
    "What did Amaan and Abdullah decide about EchoMind?",
    "PostgreSQL decision",
    "recent discussions",
]

SEPARATOR = "=" * 70


def run_demo() -> None:
    session = SessionLocal()
    try:
        for query_text in QUERIES:
            print(f"\n{SEPARATOR}")
            print(f"  QUERY: {query_text}")
            print(SEPARATOR)

            query = RetrievalQuery(query_text=query_text, user_id=1, top_k=5)
            result = retrieve_context(session, query)

            print(f"\n  Events ({len(result.relevant_events)}):")
            for ev in result.relevant_events:
                print(f"    - [{ev.event_type}] {ev.title} (salience: {ev.salience_score:.2f})")
                if ev.summary:
                    print(f"      Summary: {ev.summary}")

            print(f"\n  Entities ({len(result.relevant_entities)}):")
            for ent in result.relevant_entities:
                print(f"    - {ent.name} ({ent.entity_type}, mentions: {ent.mention_count})")

            print(f"\n  Supporting Chunks ({len(result.supporting_chunks)}):")
            for chunk in result.supporting_chunks:
                preview = chunk.content[:100] + "..." if len(chunk.content) > 100 else chunk.content
                print(f"    - [{chunk.source_type}] {preview}")

            print(f"\n  Context Summary:")
            for line in result.context_summary.split("\n"):
                print(f"    {line}")

        print(f"\n{SEPARATOR}")
        print("  Demo complete.")
        print(SEPARATOR)

    finally:
        session.close()


if __name__ == "__main__":
    run_demo()
