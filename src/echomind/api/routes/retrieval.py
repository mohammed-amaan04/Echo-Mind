"""Retrieval API endpoint — query EchoMind's memory."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from echomind.db.session import SessionLocal
from echomind.retrieval import RetrievalQuery, retrieve_context

router = APIRouter(tags=["retrieval"])


def _get_db():
    """Provide a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Request / Response schemas ───────────────────────────────────────────────


class RetrievalRequest(BaseModel):
    query_text: str = Field(..., min_length=1, description="Natural-language query")
    user_id: int = Field(..., description="User ID to scope the search")
    top_k: int = Field(default=10, ge=1, le=50, description="Max results to return")


class EventOut(BaseModel):
    id: int
    title: str
    summary: str | None = None
    event_type: str
    salience_score: float
    start_time: str | None = None

    class Config:
        from_attributes = True


class EntityOut(BaseModel):
    id: int
    name: str
    entity_type: str
    mention_count: int
    salience_score: float

    class Config:
        from_attributes = True


class ChunkOut(BaseModel):
    id: int
    source_type: str
    content: str
    timestamp: str | None = None

    class Config:
        from_attributes = True


class RetrievalResponse(BaseModel):
    relevant_events: list[EventOut]
    relevant_entities: list[EntityOut]
    supporting_chunks: list[ChunkOut]
    context_summary: str


# ── Endpoint ─────────────────────────────────────────────────────────────────


@router.post("/retrieve", response_model=RetrievalResponse)
def retrieve(request: RetrievalRequest, db: Session = Depends(_get_db)):
    """Query EchoMind's memory and retrieve relevant context."""
    query = RetrievalQuery(
        query_text=request.query_text,
        user_id=request.user_id,
        top_k=request.top_k,
    )
    result = retrieve_context(db, query)

    return RetrievalResponse(
        relevant_events=[
            EventOut(
                id=e.id,
                title=e.title,
                summary=e.summary,
                event_type=e.event_type,
                salience_score=e.salience_score,
                start_time=e.start_time.isoformat() if e.start_time else None,
            )
            for e in result.relevant_events
        ],
        relevant_entities=[
            EntityOut(
                id=ent.id,
                name=ent.name,
                entity_type=ent.entity_type,
                mention_count=ent.mention_count,
                salience_score=ent.salience_score,
            )
            for ent in result.relevant_entities
        ],
        supporting_chunks=[
            ChunkOut(
                id=c.id,
                source_type=c.source_type,
                content=c.content,
                timestamp=c.timestamp.isoformat() if c.timestamp else None,
            )
            for c in result.supporting_chunks
        ],
        context_summary=result.context_summary,
    )
