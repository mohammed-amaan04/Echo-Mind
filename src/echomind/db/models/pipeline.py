from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from echomind.db.base import Base


class ProcessingQueueEntry(Base):
    __tablename__ = "processing_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    memory_chunk_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("memory_chunks.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(String(20), server_default="pending", nullable=False)
    retry_count: Mapped[int] = mapped_column(Integer, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class FailedJob(Base):
    __tablename__ = "failed_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    memory_chunk_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("memory_chunks.id", ondelete="SET NULL"), nullable=True
    )
    failure_reason: Mapped[str] = mapped_column(Text, nullable=False)
    stage: Mapped[str] = mapped_column(String(100), nullable=False)
    reference_ids: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), server_default="running")
    records_processed: Mapped[int] = mapped_column(Integer, server_default="0")
