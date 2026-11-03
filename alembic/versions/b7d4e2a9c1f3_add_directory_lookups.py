"""Segment 20H Item 6 — add directory_lookups

The directory answers an upload's countdown fetched, kept fifteen
minutes so the upload reads them rather than asking Graph again
(``guide/segment_20H_walkthrough_19Z_followups.md`` Item 6). One row per
operator, session and lookup key; both FKs ``ON DELETE CASCADE``.

A single new table: ``create_table`` / ``drop_table`` round-trip on
SQLite and Postgres. The downgrade drops the indexes by the names the
upgrade gave them before the table.

Revision ID: b7d4e2a9c1f3
Revises: e4b2c7a91d36
Create Date: 2026-11-03
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7d4e2a9c1f3"
down_revision: str | Sequence[str] | None = "e4b2c7a91d36"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "directory_lookups",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("operator_user_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=320), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("match_type", sa.String(length=32), nullable=False),
        sa.Column("note", sa.String(length=255), nullable=False),
        sa.Column("account_id", sa.String(length=64), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("mail", sa.String(length=320), nullable=True),
        sa.Column("upn", sa.String(length=320), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["operator_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "operator_user_id", "session_id", "key",
            name="uq_directory_lookups_operator_session_key",
        ),
    )
    op.create_index(
        "ix_directory_lookups_operator_user_id", "directory_lookups", ["operator_user_id"]
    )
    op.create_index("ix_directory_lookups_session_id", "directory_lookups", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_directory_lookups_session_id", table_name="directory_lookups")
    op.drop_index("ix_directory_lookups_operator_user_id", table_name="directory_lookups")
    op.drop_table("directory_lookups")
