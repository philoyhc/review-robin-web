"""Segment 18P PR G2 — add rehydrate_stashes

Server-side stash of an uploaded extract file set, held between the
rehydrate Validate and Commit requests (``docs/rehydrate.md`` §3.3).
Postgres-backed so the two-request hand-off survives App Service
scale-out. ``payload`` is a portable ``LargeBinary`` (SQLite BLOB /
Postgres bytea) — no dialect-specific column type.

Single new table with a unique ``token`` and an ``operator_user_id`` FK
(``ON DELETE CASCADE``). Portable both directions: ``create_table`` /
``drop_table`` round-trip cleanly on SQLite and Postgres.

Revision ID: a3f1c7e9b204
Revises: c4e7d2a8f165
Create Date: 2026-06-05
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a3f1c7e9b204"
down_revision: Union[str, Sequence[str], None] = "c4e7d2a8f165"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "rehydrate_stashes",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("operator_user_id", sa.Integer(), nullable=False),
        sa.Column("payload", sa.LargeBinary(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["operator_user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rehydrate_stashes_operator_user_id",
        "rehydrate_stashes",
        ["operator_user_id"],
    )
    op.create_index(
        "ix_rehydrate_stashes_token",
        "rehydrate_stashes",
        ["token"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_rehydrate_stashes_token", table_name="rehydrate_stashes"
    )
    op.drop_index(
        "ix_rehydrate_stashes_operator_user_id",
        table_name="rehydrate_stashes",
    )
    op.drop_table("rehydrate_stashes")
