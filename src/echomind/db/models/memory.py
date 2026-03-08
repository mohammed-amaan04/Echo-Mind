from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from echomind.db.base import Base

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2


class MemoryChunk(Base):
    __tablename__ = "memory_chunks"
    __table_args__ = (Index("ix_memory_chunks_timestamp", "timestamp"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    external_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    participants: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    embedding = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    initial_salience: Mapped[float | None] = mapped_column(Float, nullable=True)
    refined_salience: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_processed: Mapped[bool] = mapped_column(Boolean, server_default="false")
    session_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
