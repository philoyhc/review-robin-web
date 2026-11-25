"""instruments.held_field_keys: the fields a linked application sent

Segment 23G rung 3 (``guide/segment_23G_linked_custom_instrument.md``): in
a ``custom`` linked instrument the fields the application sent are held,
known by key, and Review Robin's own fields are free. The list is written
at the create and by each re-send; null on every existing instrument,
which the next re-send fills. The downgrade drops it.

Revision ID: b8e4f0a3c5d9
Revises: a7d3e9f2b4c8
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b8e4f0a3c5d9"
down_revision: str | Sequence[str] | None = "a7d3e9f2b4c8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.add_column(sa.Column("held_field_keys", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.drop_column("held_field_keys")
