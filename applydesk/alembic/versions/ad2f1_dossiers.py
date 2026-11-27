"""AD2F: dossiers

Revision ID: ad2f1dossiers
Revises: ad2j1applications
Create Date: 2026-11-26

The dossier as its own record (segment AD2F,
`applydesk/guide/archive/segment_AD2F_dossiers.md`; rulings 32, 81; AD-44): its
own public ID, and its source, an application or a Candidates row, exactly
one of the two, each at most once.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ad2f1dossiers"
down_revision: str | Sequence[str] | None = "ad2j1applications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dossier",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("public_id", sa.String(length=10), nullable=False),
        sa.Column("exercise_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=True),
        sa.Column("candidate_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "(application_id IS NULL) <> (candidate_id IS NULL)", name="ck_dossier_one_source"
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["application.id"], name="fk_dossier_application"
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate.id"], name="fk_dossier_candidate"),
        sa.ForeignKeyConstraint(["exercise_id"], ["exercise.id"], name="fk_dossier_exercise"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_dossier_application"),
        sa.UniqueConstraint("candidate_id", name="uq_dossier_candidate"),
        sa.UniqueConstraint("public_id", name="uq_dossier_public_id"),
    )
    with op.batch_alter_table("dossier", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_dossier_exercise_id"), ["exercise_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("dossier", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_dossier_exercise_id"))
    op.drop_table("dossier")
