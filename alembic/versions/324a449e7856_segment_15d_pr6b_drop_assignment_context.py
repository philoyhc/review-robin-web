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

import sqlalchemy as sa
from alembic import op


revision: str = "324a449e7856"
down_revision: Union[str, Sequence[str], None] = "e43454fceb1c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("assignments") as batch:
        batch.drop_column("context")


def downgrade() -> None:
    # Round-trip-friendly downgrade: re-create the JSON column as
    # nullable. The data the column held is gone (PR 5 lifted
    # ``pair_context_*`` to the relationships table; the
    # ``assignment_context_*`` keys retired entirely), so the
    # column comes back empty. The CI round-trip gate
    # (``alembic downgrade base`` then ``upgrade head``) needs the
    # downgrade to succeed even though the data lift is one-way.
    with op.batch_alter_table("assignments") as batch:
        batch.add_column(sa.Column("context", sa.JSON(), nullable=True))
