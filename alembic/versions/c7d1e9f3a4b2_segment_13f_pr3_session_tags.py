"""segment 13f pr3: session_tags

Adds the per-session free-form tag table. Each row is one
operator-chosen tag on one session; ``(session_id, tag)`` is
unique so a session cannot carry the same tag twice, and the FK
is ``ON DELETE CASCADE`` so deleting a session drops its tags.

Lands inert — no service module reads or writes the table until
Segment 18A Part 2 lights it up (lobby tag-filter chips + the
Add / Remove tag affordance). See
``guide/archive/segment_13F_more_db_prep.md`` PR 3 for the schema
rationale.

Revision ID: c7d1e9f3a4b2
Revises: e9277c43b251
Create Date: 2026-05-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c7d1e9f3a4b2"
down_revision: Union[str, Sequence[str], None] = "e9277c43b251"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "session_tags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("tag", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "session_id", "tag", name="uq_session_tag_session_tag"
        ),
    )


def downgrade() -> None:
    op.drop_table("session_tags")
