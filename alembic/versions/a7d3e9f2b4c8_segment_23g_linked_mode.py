"""instruments.linked_mode: a linked instrument's gate type

Segment 23G rung 2 (``guide/segment_23G_linked_custom_instrument.md``): a
linked instrument is ``locked`` (fixed whole, as 23F made it) or
``custom`` (its fields held, Review Robin may reorder, require, add and
branch). Every existing instrument takes ``locked``, so nothing changes;
the column is read only under the instrument lock. The downgrade drops it.

Revision ID: a7d3e9f2b4c8
Revises: e5f9b3a7c2d4
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a7d3e9f2b4c8"
down_revision: str | Sequence[str] | None = "e5f9b3a7c2d4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.add_column(
            sa.Column("linked_mode", sa.String(8), server_default="locked", nullable=False)
        )


def downgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.drop_column("linked_mode")
