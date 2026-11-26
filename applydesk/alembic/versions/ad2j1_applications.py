"""AD2J: applications

Revision ID: ad2j1applications
Revises: ad2s1gatescale
Create Date: 2026-11-26

An exercise's applications move from code into the database (segment
AD2J, `applydesk/guide/segment_AD2J_applications.md`; AD-38): the
applicant a person, the state `draft`, `submitted` or `withdrawn` with the
time of each move, and the form revision an application answered.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ad2j1applications"
down_revision: str | Sequence[str] | None = "ad2s1gatescale"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "application",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=10), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("state", sa.String(length=10), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdraw_reason", sa.String(length=500), nullable=False),
        sa.Column("form_revision", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercise.id"], name="fk_application_exercise"),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"], name="fk_application_person"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id", name="uq_application_public_id"),
    )
    with op.batch_alter_table("application", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_application_exercise_id"), ["exercise_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_application_person_id"), ["person_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("application", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_application_person_id"))
        batch_op.drop_index(batch_op.f("ix_application_exercise_id"))
    op.drop_table("application")
