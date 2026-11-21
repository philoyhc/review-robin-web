"""AD2A: at most one Owner row per exercise

Revision ID: ad2a2oneowner
Revises: ad2a1foundations
Create Date: 2026-11-21

A partial unique index, so two concurrent handovers cannot leave two
Owners (Codex on #4110). Partial indexes are SQLite's and Postgres's both.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ad2a2oneowner"
down_revision = "ad2a1foundations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_exercise_one_owner",
        "exercise_operator",
        ["exercise_id"],
        unique=True,
        sqlite_where=sa.text("is_owner"),
        postgresql_where=sa.text("is_owner"),
    )


def downgrade() -> None:
    op.drop_index("uq_exercise_one_owner", table_name="exercise_operator")
