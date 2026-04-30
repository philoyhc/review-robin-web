"""segment 10a: help_text + help_text_visible on instrument_response_fields

Revision ID: 4e8a2b9c3d11
Revises: 7d4f5b3c1a92
Create Date: 2026-04-30 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "4e8a2b9c3d11"
down_revision: Union[str, Sequence[str], None] = "7d4f5b3c1a92"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instrument_response_fields", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("help_text", sa.Text(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "help_text_visible",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("instrument_response_fields", schema=None) as batch_op:
        batch_op.drop_column("help_text_visible")
        batch_op.drop_column("help_text")
