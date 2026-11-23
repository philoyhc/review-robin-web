"""AD2D: the form's cards and the exercise's form heading

Revision ID: ad2d1form
Revises: ad2e1panels
Create Date: 2026-11-23

An exercise's form in the database (segment AD2D,
`applydesk/guide/archive/segment_AD2D_form.md`): `form_card`, one row per field,
section or page break, keyed per exercise (`q<n>`, never reused) so a rule
names a question by its key (AD-45); and the exercise's `form_title`,
`form_description` and `form_revision`, 0 until Form is first saved. New
tables and columns only: nothing reads them until the store does.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ad2d1form"
down_revision: str | Sequence[str] | None = "ad2e1panels"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "form_card",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=40), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("type", sa.String(length=16), nullable=False),
        sa.Column("label", sa.String(length=500), nullable=False),
        sa.Column("help", sa.Text(), nullable=False),
        sa.Column("min", sa.String(length=40), nullable=False),
        sa.Column("max", sa.String(length=40), nullable=False),
        sa.Column("step", sa.String(length=40), nullable=False),
        sa.Column("options", sa.Text(), nullable=False),
        sa.Column("exclusive", sa.Boolean(), nullable=False),
        sa.Column("ratio_w", sa.String(length=6), nullable=False),
        sa.Column("ratio_h", sa.String(length=6), nullable=False),
        sa.Column("pool", sa.String(length=80), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("shown", sa.Boolean(), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercise.id"], name="fk_form_card_exercise"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exercise_id", "key", name="uq_form_card_key"),
    )
    with op.batch_alter_table("form_card", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_form_card_exercise_id"), ["exercise_id"], unique=False)

    with op.batch_alter_table("exercise", schema=None) as batch_op:
        batch_op.add_column(sa.Column("form_title", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("form_description", sa.Text(), nullable=True))
        batch_op.add_column(
            sa.Column("form_revision", sa.Integer(), server_default="0", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("exercise", schema=None) as batch_op:
        batch_op.drop_column("form_revision")
        batch_op.drop_column("form_description")
        batch_op.drop_column("form_title")

    with op.batch_alter_table("form_card", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_form_card_exercise_id"))

    op.drop_table("form_card")
