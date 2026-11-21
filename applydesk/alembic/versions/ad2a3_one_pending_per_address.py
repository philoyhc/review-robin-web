"""AD2A: at most one pending person per address

Revision ID: ad2a3onepending
Revises: ad2a2oneowner
Create Date: 2026-11-21

A partial unique index on person.email_key where object_id is null, so two
requests adding one address at once cannot make two pending people (Codex
on #4110). Bound people are outside it: their address is a snapshot.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ad2a3onepending"
down_revision = "ad2a2oneowner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_person_pending_email",
        "person",
        ["email_key"],
        unique=True,
        sqlite_where=sa.text("object_id IS NULL"),
        postgresql_where=sa.text("object_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_person_pending_email", table_name="person")
