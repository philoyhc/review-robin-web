"""instrument_response_fields.scale and scale_labels: a scale answer

Segment 20P Item 1 (``guide/segment_20P_scale_answer.md``): an Integer or
Decimal response field may answer as a scale. ``scale`` is false on every
existing field, so nothing changes until an operator chooses one;
``scale_labels`` is nullable. The downgrade drops both.

Revision ID: e5f9b3a7c2d4
Revises: d4e7a2c9f1b3
Create Date: 2026-11-24
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e5f9b3a7c2d4"
down_revision: str | Sequence[str] | None = "d4e7a2c9f1b3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("instrument_response_fields") as batch:
        batch.add_column(
            sa.Column("scale", sa.Boolean(), server_default=sa.false(), nullable=False)
        )
        batch.add_column(sa.Column("scale_labels", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("instrument_response_fields") as batch:
        batch.drop_column("scale_labels")
        batch.drop_column("scale")
