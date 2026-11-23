"""AD2L: email ticks and templates

Revision ID: ad2l1emails
Revises: ad2d1form
Create Date: 2026-11-23

An exercise's emails in the database (segment AD2L,
`applydesk/guide/archive/segment_AD2L_emails.md`): `email_send`, a row per
(item, audience) Process ticks, retired when unticked; `email_template`,
a row per (item, audience) with its subject, body and the version its
saves count; and `exercise.sends_saved`, false until Process records its
ticks. New tables and a column only: nothing reads them until the store
does.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ad2l1emails"
down_revision: str | Sequence[str] | None = "ad2d1form"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "email_send",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("item", sa.String(length=40), nullable=False),
        sa.Column("audience", sa.String(length=16), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercise.id"], name="fk_email_send_exercise"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exercise_id", "item", "audience", name="uq_email_send_pair"),
    )
    with op.batch_alter_table("email_send", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_email_send_exercise_id"), ["exercise_id"], unique=False
        )

    op.create_table(
        "email_template",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("item", sa.String(length=40), nullable=False),
        sa.Column("audience", sa.String(length=16), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("saved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["exercise_id"], ["exercise.id"], name="fk_email_template_exercise"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exercise_id", "item", "audience", name="uq_email_template_pair"),
    )
    with op.batch_alter_table("email_template", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_email_template_exercise_id"), ["exercise_id"], unique=False
        )

    with op.batch_alter_table("exercise", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("sends_saved", sa.Boolean(), server_default=sa.false(), nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("exercise", schema=None) as batch_op:
        batch_op.drop_column("sends_saved")

    with op.batch_alter_table("email_template", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_email_template_exercise_id"))

    op.drop_table("email_template")
    with op.batch_alter_table("email_send", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_email_send_exercise_id"))

    op.drop_table("email_send")
