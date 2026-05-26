"""Add instruments.band1_touched_links

Adds a per-instrument JSON column that records which Band 1 link
pills the operator has deliberately clicked into a set state.
Empty list (or NULL) means the operator has not yet touched any
of the three Band 1 link pills — the workflow card surfaces this
as an unconfigured instrument so the operator can't accidentally
ship the default Full Matrix without explicit intent.

Stored values: list of ``"link1"`` / ``"link2"`` / ``"link3"``
strings. Persistence is sticky (once touched, always touched).

Backfill: existing instruments are treated as untouched
(``NULL`` reads as empty). Sessions previously deemed configured
will surface as unconfigured on the workflow card after deploy
until the operator visits the Instruments page and clicks each
Band 1 pill — the deliberate safety gate this column introduces.

Revision ID: a3f7e2d1c9b5
Revises: e1a7b3c9d2f8
Create Date: 2026-05-26
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a3f7e2d1c9b5"
down_revision: Union[str, Sequence[str], None] = "e1a7b3c9d2f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("band1_touched_links", sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.drop_column("band1_touched_links")
