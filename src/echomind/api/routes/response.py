"""Response API endpoint — ask EchoMind a question.

This is the unified endpoint that combines retrieval (Phase 4) and
response generation (Phase 5) into a single call.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from echomind.db.session import SessionLocal
from echomind.response import ResponseRequest, generate_response
from echomind.retrieval import RetrievalQuery, retrieve_context

router = APIRouter(tags=["response"])


def _get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Request / Response schemas ───────────────────────────────────────────────


class AskRequest(BaseModel):
    query_text: str = Field(..., min_length=1, description="Natural-language question")
    user_id: int = Field(..., description="User ID")
    top_k: int = Field(default=5, ge=1, le=20, description="Max context items")


class ActionOut(BaseModel):
    action_type: str
    description: str
    payload: dict = Field(default_factory=dict)


class AskResponse(BaseModel):
    answer: str
    supporting_events: list[int]
    supporting_entities: list[int]
    confidence_score: float
    suggested_actions: list[ActionOut]


# ── Endpoint ─────────────────────────────────────────────────────────────────


@router.post("/ask", response_model=AskResponse)
def ask(request: AskRequest, db: Session = Depends(_get_db)):
    """Ask EchoMind a question — retrieves context and generates a response."""
    # Step 1: Retrieve context
    retrieval_query = RetrievalQuery(
        query_text=request.query_text,
        user_id=request.user_id,
        top_k=request.top_k,
    )
    retrieval_result = retrieve_context(db, retrieval_query)

    # Step 2: Generate response
    response_request = ResponseRequest(
        query_text=request.query_text,
        retrieval_result=retrieval_result,
        user_id=request.user_id,
    )
    output = generate_response(response_request)

    return AskResponse(
        answer=output.answer,
        supporting_events=output.supporting_events,
        supporting_entities=output.supporting_entities,
        confidence_score=output.confidence_score,
        suggested_actions=[
            ActionOut(
                action_type=a.action_type,
                description=a.description,
                payload=a.payload,
            )
            for a in output.suggested_actions
        ],
    )
