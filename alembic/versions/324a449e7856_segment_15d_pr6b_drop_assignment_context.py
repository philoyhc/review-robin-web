"""segment 15d pr6b: drop assignments.context JSON column

Destructive migration. PR 5 backfilled the only consuming keys
(``pair_context_1``/``2``/``3``) into the new ``relationships``
table; ``assignment_context_1``/``2``/``3`` retire entirely
(operator-typed via the manual CSV only, with no rule-engine or
display-field consumer post-15D). Drops the column outright.

No backfill or downgrade — the destination is "the column does
not exist". Runs after PR 5 in the chain so the data has
already moved by the time this fires.

Revision ID: 324a449e7856
Revises: e43454fceb1c
Create Date: 2026-05-10

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "324a449e7856"
down_revision: Union[str, Sequence[str], None] = "e43454fceb1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("assignments") as batch:
        batch.drop_column("context")


def downgrade() -> None:
    # Re-creating an empty JSON column is technically possible, but
    # the data the column held is gone — the column comes back blank
    # and 15D's rule engine reads pair_context from ``relationships``
    # anyway. We mark the migration one-way.
    raise RuntimeError(
        "downgrade not supported — Assignment.context column drop is "
        "one-way (data already lifted to relationships in PR 5)."
    )
