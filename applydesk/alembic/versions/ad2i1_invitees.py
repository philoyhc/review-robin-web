"""AD2I: a Form's invitees

Revision ID: ad2i1invitees
Revises: ad2k1entries
Create Date: 2026-11-27

Ruling 84 (segment AD2I, `applydesk/guide/segment_AD2I_who_may_apply.md`):
a Form's invite list as its own table, a person who may submit, listed once
per exercise. An exercise already Invitation only with Create dossiers on a
stage holding the Form has those entries' people moved onto the list; the
entries stay.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ad2i1invitees"
down_revision: str | Sequence[str] | None = "ad2k1entries"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "invitee",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("via", sa.String(length=8), nullable=False),
        sa.Column("added_by_id", sa.Integer(), nullable=True),
        sa.Column("added_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["added_by_id"], ["person.id"], name="fk_invitee_added_by"),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercise.id"], name="fk_invitee_exercise"),
        sa.ForeignKeyConstraint(["person_id"], ["person.id"], name="fk_invitee_person"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("exercise_id", "person_id", name="uq_invitee_pair"),
    )
    with op.batch_alter_table("invitee", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_invitee_exercise_id"), ["exercise_id"], unique=False)
    # The roster an Invitation only exercise kept on its Form's stage, as
    # invitees: each person once, from their earliest live entry (the
    # lowest id), its via, actor and time together.
    op.execute(
        sa.text(
            """
            INSERT INTO invitee (exercise_id, person_id, via, added_by_id, added_at)
            SELECT c.exercise_id, c.person_id, c.via, c.added_by_id, c.added_at
            FROM candidate c
            WHERE c.id IN (
              SELECT MIN(c2.id)
              FROM candidate c2
              JOIN exercise e ON e.id = c2.exercise_id
              WHERE e.eligibility = 'invitation'
                AND c2.removed_at IS NULL
                AND EXISTS (
                  SELECT 1 FROM stage s
                  WHERE s.exercise_id = c2.exercise_id AND s.retired_at IS NULL
                    AND s.holds_form IS TRUE AND s.holds_candidates IS TRUE
                )
              GROUP BY c2.exercise_id, c2.person_id
            )
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("invitee", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_invitee_exercise_id"))
    op.drop_table("invitee")
