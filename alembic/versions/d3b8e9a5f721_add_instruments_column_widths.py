"""add instruments.column_widths

Adds a nullable JSON column ``instruments.column_widths`` that
stores per-column pixel widths the operator sets by drag-resizing
the Band 2 preview table on a new-model instrument. Keys: ``identity``
for the always-rendered Reviewee / Group identity column,
``df_{display_field_id}`` for each display field column. Values are
positive integers in pixels. Missing keys mean "use the
auto-sized default". When at least one width is set, the
reviewer-surface table opts into ``table-layout: fixed`` so the
widths take hold.

See ``guide/instrument_builder.md`` for the Band 2 design.

Revision ID: d3b8e9a5f721
Revises: c9a5f3e7b240
Create Date: 2026-05-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3b8e9a5f721"
down_revision: Union[str, Sequence[str], None] = "c9a5f3e7b240"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("column_widths", sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.drop_column("column_widths")
