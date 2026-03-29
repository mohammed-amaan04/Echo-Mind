"""End-to-end demo — show output of each EchoMind layer.

Requires: docker compose up, alembic upgrade head, seed_phase3.py, seed_phase4.py

Run:
    python scripts/demo_full_pipeline.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from echomind.db.session import SessionLocal
from echomind.retrieval import RetrievalQuery, retrieve_context
from echomind.response import ResponseRequest, generate_response

SEP = "=" * 70
THIN = "-" * 70


def run_demo() -> None:
    session = SessionLocal()
    query_text = "What did Amaan and Abdullah decide about EchoMind?"
    user_id = 1

    print(f"\n{SEP}")
    print(f"  ECHOMIND FULL PIPELINE DEMO")
    print(f"  Query: \"{query_text}\"")
    print(SEP)

    # ══════════════════════════════════════════════════════════════════
    # LAYER 1 — Persistence Layer (Phase 3) — what's already in the DB
    # ══════════════════════════════════════════════════════════════════
    print(f"\n{THIN}")
    print("  LAYER 1: PERSISTENCE LAYER (Phase 3) — Knowledge Graph in DB")
    print(THIN)

    from sqlalchemy import text

    # Show entities
    rows = session.execute(text("SELECT id, name, entity_type, mention_count, salience_score FROM entities ORDER BY mention_count DESC")).fetchall()
    print(f"\n  Entities in DB ({len(rows)}):")
    for r in rows:
        print(f"    [{r.id}] {r.name} ({r.entity_type}) — {r.mention_count} mentions, salience={r.salience_score:.2f}")

    # Show events
    rows = session.execute(text("SELECT id, title, event_type, salience_score, start_time FROM events ORDER BY start_time")).fetchall()
    print(f"\n  Events in DB ({len(rows)}):")
    for r in rows:
        ts = r.start_time.strftime("%Y-%m-%d %H:%M") if r.start_time else "?"
        print(f"    [{r.id}] [{r.event_type}] {r.title} — salience={r.salience_score:.2f}, {ts}")

    # Show links
    link_count = session.execute(text("SELECT COUNT(*) FROM entity_event_links")).scalar()
    chunk_link_count = session.execute(text("SELECT COUNT(*) FROM event_memory_links")).scalar()
    print(f"\n  Graph Links: {link_count} entity→event, {chunk_link_count} event→chunk")

    # Show chunks with embeddings
    embed_count = session.execute(text("SELECT COUNT(*) FROM memory_chunks WHERE embedding IS NOT NULL")).scalar()
    total_count = session.execute(text("SELECT COUNT(*) FROM memory_chunks")).scalar()
    print(f"  Memory Chunks: {total_count} total, {embed_count} with embeddings")

    # ══════════════════════════════════════════════════════════════════
    # LAYER 2 — Retrieval Layer (Phase 4) — context reconstruction
    # ══════════════════════════════════════════════════════════════════
    print(f"\n{THIN}")
    print("  LAYER 2: RETRIEVAL LAYER (Phase 4) — Context Reconstruction")
    print(THIN)

    query = RetrievalQuery(query_text=query_text, user_id=user_id, top_k=5)
    retrieval_result = retrieve_context(session, query)

    print(f"\n  Retrieved Events ({len(retrieval_result.relevant_events)}):")
    for ev in retrieval_result.relevant_events:
        print(f"    [{ev.event_type}] {ev.title} (salience: {ev.salience_score:.2f})")

    print(f"\n  Retrieved Entities ({len(retrieval_result.relevant_entities)}):")
    for ent in retrieval_result.relevant_entities:
        print(f"    {ent.name} ({ent.entity_type}, mentions: {ent.mention_count})")

    print(f"\n  Supporting Chunks ({len(retrieval_result.supporting_chunks)}):")
    for chunk in retrieval_result.supporting_chunks:
        preview = chunk.content[:80] + "..." if len(chunk.content) > 80 else chunk.content
        print(f"    [{chunk.source_type}] {preview}")

    print(f"\n  Context Summary:")
    for line in retrieval_result.context_summary.split("\n"):
        print(f"    {line}")

    # ══════════════════════════════════════════════════════════════════
    # LAYER 3 — Response Layer (Phase 5) — LLM reasoning + actions
    # ══════════════════════════════════════════════════════════════════
    print(f"\n{THIN}")
    print("  LAYER 3: RESPONSE LAYER (Phase 5) — LLM Reasoning + Actions")
    print(THIN)

    request = ResponseRequest(
        query_text=query_text,
        retrieval_result=retrieval_result,
        user_id=user_id,
    )
    response = generate_response(request)

    print(f"\n  Answer:")
    for line in response.answer.split("\n"):
        print(f"    {line}")

    print(f"\n  Confidence Score: {response.confidence_score:.3f}")
    print(f"  Supporting Event IDs: {response.supporting_events}")
    print(f"  Supporting Entity IDs: {response.supporting_entities}")

    print(f"\n  Suggested Actions ({len(response.suggested_actions)}):")
    for action in response.suggested_actions:
        print(f"    [{action.action_type}] {action.description}")
        if action.payload:
            for k, v in action.payload.items():
                print(f"      {k}: {v}")

    print(f"\n{SEP}")
    print("  Demo complete.")
    print(SEP)

    session.close()


if __name__ == "__main__":
    run_demo()
