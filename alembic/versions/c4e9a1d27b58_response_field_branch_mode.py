"""19T Item 13: a branch's mode on the parent response field

Adds one nullable column to ``instrument_response_fields``
(``guide/segment_19T_advanced_instruments.md`` Item 13):

- ``branch_mode`` — on a parent, what its condition does to the
  governed fields: ``show`` (19T Item 10's kind) or ``require``
  (required while the condition holds, else optional). Null reads
  ``show``, so every saved branch keeps its meaning.

Lands inert: nullable, no backfill, and no write path accepts the mode
until the rule reads it (Item 13 rung 3).

Revision ID: c4e9a1d27b58
Revises: 63b1bb107eb0
Create Date: 2026-09-28

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c4e9a1d27b58"
down_revision: Union[str, Sequence[str], None] = "63b1bb107eb0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instrument_response_fields") as batch:
        batch.add_column(
            sa.Column("branch_mode", sa.String(length=8), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("instrument_response_fields") as batch:
        batch.drop_column("branch_mode")
