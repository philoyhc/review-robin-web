"""segment 11L: add Instrument.short_label

Revision ID: e1c8f4d57a92
Revises: b2c3d4e5f6a7
Create Date: 2026-05-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e1c8f4d57a92"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add nullable instruments.short_label (VARCHAR(32)).

    Reviewer-facing operator-set framing per Segment 11L. Additive,
    nullable; existing rows pick up NULL by default. The reviewer
    surface falls back to bare `Page #{N}` when short_label is NULL
    or empty (PR γ of the multi-instrument rewrite consumes this).
    """
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("short_label", sa.String(length=32), nullable=True)
        )


def downgrade() -> None:
    """Drop instruments.short_label."""
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.drop_column("short_label")
