"""sessions.symmetric_review; reviewees.mirrors_reviewer_id

Segment 20B rung 2 (``guide/segment_20B_symmetric_review.md``): a
per-session Symmetric review setting, off by default, under which the
Reviewers roster is the only one edited and every write mirrors to
Reviewees. ``reviewees.mirrors_reviewer_id`` links a mirrored reviewee to
its reviewer, so an address correction updates the same row rather than
reading as one person removed and another added. Nullable, indexed, and
``ON DELETE SET NULL``: the reconcile (rung 3) deletes a gone reviewer's
reviewee itself; the rule only keeps a delete that bypasses it from
failing on Postgres.

Revision ID: b2f8d4a6c1e9
Revises: a7d3e9f1c2b5
Create Date: 2026-11-01
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b2f8d4a6c1e9"
down_revision: Union[str, Sequence[str], None] = "a7d3e9f1c2b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FK = "fk_reviewees_mirrors_reviewer_id_reviewers"
_IX = "ix_reviewees_mirrors_reviewer_id"


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(
            sa.Column(
                "symmetric_review",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )
    with op.batch_alter_table("reviewees") as batch:
        batch.add_column(sa.Column("mirrors_reviewer_id", sa.Integer(), nullable=True))
        batch.create_index(_IX, ["mirrors_reviewer_id"])
        batch.create_foreign_key(
            _FK, "reviewers", ["mirrors_reviewer_id"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    with op.batch_alter_table("reviewees") as batch:
        batch.drop_constraint(_FK, type_="foreignkey")
        batch.drop_index(_IX)
        batch.drop_column("mirrors_reviewer_id")
    with op.batch_alter_table("sessions") as batch:
        batch.drop_column("symmetric_review")
