"""Initial schema — all EchoMind tables

Revision ID: 001
Revises: None
Create Date: 2026-03-07
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 384


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── users ──────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("email", sa.String(255), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── user_profile ───────────────────────────────────────────────────
    op.create_table(
        "user_profile",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"),
            unique=True, nullable=False,
        ),
        sa.Column("bio", sa.Text, nullable=True),
        sa.Column("timezone", sa.String(50), server_default="UTC"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── user_preferences ───────────────────────────────────────────────
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("pref_key", sa.String(100), nullable=False),
        sa.Column("pref_value", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── sessions ───────────────────────────────────────────────────────
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── data_sources ───────────────────────────────────────────────────
    op.create_table(
        "data_sources",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("config", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── user_integrations ──────────────────────────────────────────────
    op.create_table(
        "user_integrations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("access_token", sa.Text, nullable=True),
        sa.Column("refresh_token", sa.Text, nullable=True),
        sa.Column("enabled", sa.Boolean, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── memory_chunks ──────────────────────────────────────────────────
    op.create_table(
        "memory_chunks",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("external_message_id", sa.String(255), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("participants", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=True),
        sa.Column("initial_salience", sa.Float, nullable=True),
        sa.Column("refined_salience", sa.Float, nullable=True),
        sa.Column("is_processed", sa.Boolean, server_default="false"),
        sa.Column(
            "session_id", sa.Integer, sa.ForeignKey("sessions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_memory_chunks_timestamp", "memory_chunks", ["timestamp"])

    # ── entities ───────────────────────────────────────────────────────
    op.create_table(
        "entities",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("mention_count", sa.Integer, server_default="1"),
        sa.Column("first_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("salience_score", sa.Float, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "normalized_name", name="uq_user_entity_name"),
    )
    op.create_index("ix_entities_name", "entities", ["name"])
    op.create_index("ix_entities_user_id", "entities", ["user_id"])

    # ── tracked_entities ───────────────────────────────────────────────
    op.create_table(
        "tracked_entities",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "entity_id", sa.Integer, sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tracked_since", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── events ─────────────────────────────────────────────────────────
    op.create_table(
        "events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("salience_score", sa.Float, nullable=False),
        sa.Column(
            "created_from_chunk_id", sa.Integer,
            sa.ForeignKey("memory_chunks.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_events_start_time", "events", ["start_time"])

    # ── entity_event_links ─────────────────────────────────────────────
    op.create_table(
        "entity_event_links",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "entity_id", sa.Integer, sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "event_id", sa.Integer, sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_entity_event_links_entity_id", "entity_event_links", ["entity_id"])
    op.create_index("ix_entity_event_links_event_id", "entity_event_links", ["event_id"])

    # ── event_memory_links ─────────────────────────────────────────────
    op.create_table(
        "event_memory_links",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "event_id", sa.Integer, sa.ForeignKey("events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "memory_chunk_id", sa.Integer,
            sa.ForeignKey("memory_chunks.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── processing_queue ───────────────────────────────────────────────
    op.create_table(
        "processing_queue",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "memory_chunk_id", sa.Integer,
            sa.ForeignKey("memory_chunks.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("retry_count", sa.Integer, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── failed_jobs ────────────────────────────────────────────────────
    op.create_table(
        "failed_jobs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "memory_chunk_id", sa.Integer,
            sa.ForeignKey("memory_chunks.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("failure_reason", sa.Text, nullable=False),
        sa.Column("stage", sa.String(100), nullable=False),
        sa.Column("reference_ids", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── ingestion_runs ─────────────────────────────────────────────────
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), server_default="running"),
        sa.Column("records_processed", sa.Integer, server_default="0"),
    )

    # ── system_logs ────────────────────────────────────────────────────
    op.create_table(
        "system_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("module", sa.String(100), nullable=False),
        sa.Column("metadata_json", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── scheduler_state ────────────────────────────────────────────────
    op.create_table(
        "scheduler_state",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("scheduler_name", sa.String(100), unique=True, nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="false"),
        sa.Column("last_heartbeat", sa.DateTime(timezone=True), nullable=True),
    )

    # ── action_history ─────────────────────────────────────────────────
    op.create_table(
        "action_history",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("metadata_json", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── semantic_models ────────────────────────────────────────────────
    op.create_table(
        "semantic_models",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("model_name", sa.String(255), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("config", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── source_chunk_ids ───────────────────────────────────────────────
    op.create_table(
        "source_chunk_ids",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "memory_chunk_id", sa.Integer,
            sa.ForeignKey("memory_chunks.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("source_chunk_ids")
    op.drop_table("semantic_models")
    op.drop_table("action_history")
    op.drop_table("scheduler_state")
    op.drop_table("system_logs")
    op.drop_table("ingestion_runs")
    op.drop_table("failed_jobs")
    op.drop_table("processing_queue")
    op.drop_table("event_memory_links")
    op.drop_index("ix_entity_event_links_event_id", "entity_event_links")
    op.drop_index("ix_entity_event_links_entity_id", "entity_event_links")
    op.drop_table("entity_event_links")
    op.drop_index("ix_events_start_time", "events")
    op.drop_table("events")
    op.drop_table("tracked_entities")
    op.drop_index("ix_entities_user_id", "entities")
    op.drop_index("ix_entities_name", "entities")
    op.drop_table("entities")
    op.drop_index("ix_memory_chunks_timestamp", "memory_chunks")
    op.drop_table("memory_chunks")
    op.drop_table("user_integrations")
    op.drop_table("data_sources")
    op.drop_table("sessions")
    op.drop_table("user_preferences")
    op.drop_table("user_profile")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
