"""Segment 19W rung 2 — add held_uploads

One uploaded file held across an ask, so the operator answers a
refusal's question without choosing the file again
(``guide/segment_19W_held_uploads.md``). One row per slot of a refused
submit, sharing a token; scoped to an operator and a session, both FKs
``ON DELETE CASCADE``. ``content`` is a portable ``LargeBinary``
(SQLite BLOB / Postgres bytea).

A single new table: ``create_table`` / ``drop_table`` round-trip on
SQLite and Postgres. The downgrade drops the indexes by the names the
upgrade gave them before the table.

Revision ID: e8b3c1d4f6a2
Revises: d2f7a3c9b5e4
Create Date: 2026-10-19
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e8b3c1d4f6a2"
down_revision: Union[str, Sequence[str], None] = "d2f7a3c9b5e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "held_uploads",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("slot", sa.String(length=32), nullable=False),
        sa.Column("operator_user_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["operator_user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["session_id"], ["sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token", "slot", name="uq_held_uploads_token_slot"),
    )
    op.create_index("ix_held_uploads_token", "held_uploads", ["token"])
    op.create_index(
        "ix_held_uploads_operator_user_id", "held_uploads", ["operator_user_id"]
    )
    op.create_index("ix_held_uploads_session_id", "held_uploads", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_held_uploads_session_id", table_name="held_uploads")
    op.drop_index("ix_held_uploads_operator_user_id", table_name="held_uploads")
    op.drop_index("ix_held_uploads_token", table_name="held_uploads")
    op.drop_table("held_uploads")
