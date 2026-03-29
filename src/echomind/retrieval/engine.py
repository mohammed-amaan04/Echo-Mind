"""Retrieval orchestrator — main entry point for the retrieval pipeline.

Coordinates query parsing, vector search, entity search, ranking,
graph expansion, and context assembly into a single call:

    ``retrieve_context(session, query) → RetrievalResult``
"""

from __future__ import annotations

import structlog
from sqlalchemy.orm import Session as DbSession

from echomind.retrieval.context_builder import build_context
from echomind.retrieval.entity_search import entity_search
from echomind.retrieval.graph_traversal import expand_graph, fetch_entities_for_events
from echomind.retrieval.query_parser import parse_query
from echomind.retrieval.ranker import rank_chunks, rank_events
from echomind.retrieval.schemas import RetrievalQuery, RetrievalResult
from echomind.retrieval.vector_search import vector_search

logger = structlog.get_logger(__name__)


def retrieve_context(session: DbSession, query: RetrievalQuery) -> RetrievalResult:
    """Execute the full retrieval pipeline and return a ``RetrievalResult``.

    Flow
    ----
    1. Parse query (entity detection, intent, time filter)
    2. Vector search (semantic similarity on memory_chunks)
    3. Entity search (graph-based event lookup)
    4. Merge candidate events
    5. Rank events by composite score
    6. Expand graph (fetch linked entities + supporting chunks)
    7. Build context summary
    """
    logger.info(
        "retrieval_start",
        query=query.query_text,
        user_id=query.user_id,
        top_k=query.top_k,
    )

    # ── Step 1: Parse query ────────────────────────────────────────────
    parsed = parse_query(session, query.query_text, query.user_id)
    logger.info(
        "query_parsed",
        intent=parsed.intent_type,
        entities=parsed.detected_entities,
        has_time_filter=parsed.time_filter is not None,
    )

    # ── Step 2: Vector search ──────────────────────────────────────────
    vector_results = vector_search(session, parsed, query.user_id, top_k=query.top_k * 2)
    vector_results = rank_chunks(vector_results, query.top_k)

    # Build chunk_id → similarity map for ranking events
    chunk_scores: dict[int, float] = {sc.chunk.id: sc.similarity for sc in vector_results}

    # ── Step 3: Entity search ──────────────────────────────────────────
    entity_events = entity_search(session, parsed, query.user_id)

    # ── Step 4: Merge candidate events ─────────────────────────────────
    seen_event_ids: set[int] = set()
    merged_events = []

    # Entity-matched events first (higher precision)
    for ev in entity_events:
        if ev.id not in seen_event_ids:
            seen_event_ids.add(ev.id)
            merged_events.append(ev)

    # Add events from vector-matched chunks (via created_from_chunk_id)
    for sc in vector_results:
        chunk = sc.chunk
        if chunk.is_processed and chunk.refined_salience is not None:
            # Find events created from this chunk
            from echomind.db.models.event import Event
            from sqlalchemy import select

            stmt = select(Event).where(Event.created_from_chunk_id == chunk.id)
            events = session.execute(stmt).scalars().all()
            for ev in events:
                if ev.id not in seen_event_ids:
                    seen_event_ids.add(ev.id)
                    merged_events.append(ev)

    # ── Step 5: Rank events ────────────────────────────────────────────
    # Fetch entity names for each event (for overlap scoring)
    event_ids = [e.id for e in merged_events]
    entity_map = fetch_entities_for_events(session, event_ids)
    event_entity_names: dict[int, set[str]] = {}
    for eid, entities in entity_map.items():
        event_entity_names[eid] = {e.normalized_name for e in entities}

    scored_events = rank_events(
        merged_events,
        event_entity_names,
        parsed.detected_entities,
        chunk_scores,
    )

    # ── Step 6: Graph expansion ────────────────────────────────────────
    top_events = [se.event for se in scored_events[: query.top_k]]
    all_entities, graph_chunks, expanded_events = expand_graph(
        session, top_events, expand_depth=1,
    )

    # Refresh entity map with expanded events
    expanded_ids = [e.id for e in expanded_events]
    full_entity_map = fetch_entities_for_events(session, expanded_ids)

    # ── Step 7: Build context ──────────────────────────────────────────
    result = build_context(
        scored_events=scored_events,
        all_entities=all_entities,
        graph_chunks=graph_chunks,
        vector_chunks=vector_results,
        event_entity_map=full_entity_map,
        top_k=query.top_k,
    )

    logger.info(
        "retrieval_complete",
        events=len(result.relevant_events),
        entities=len(result.relevant_entities),
        chunks=len(result.supporting_chunks),
    )
    return result
