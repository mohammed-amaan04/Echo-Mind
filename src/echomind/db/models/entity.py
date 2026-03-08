from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from echomind.db.base import Base


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("user_id", "normalized_name", name="uq_user_entity_name"),
        Index("ix_entities_name", "name"),
        Index("ix_entities_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    mention_count: Mapped[int] = mapped_column(Integer, server_default="1")
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    salience_score: Mapped[float] = mapped_column(Float, server_default="0.0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TrackedEntity(Base):
    __tablename__ = "tracked_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    entity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    tracked_since: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
