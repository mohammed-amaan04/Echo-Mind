"""Add media_files table

Revision ID: 002
Revises: 001
Create Date: 2026-04-25
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "media_files",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "memory_chunk_id", sa.Integer,
            sa.ForeignKey("memory_chunks.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("file_name", sa.String(500), nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("storage_url", sa.String(1000), nullable=True),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_media_files_memory_chunk_id", "media_files", ["memory_chunk_id"])


def downgrade() -> None:
    op.drop_index("ix_media_files_memory_chunk_id", "media_files")
    op.drop_table("media_files")
