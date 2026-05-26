"""add instruments.is_pilot

Adds a boolean ``instruments.is_pilot`` column (default False) so the
Instrument Builder concept-test card can be persisted alongside
ordinary instruments. Pilot instruments behave exactly like ordinary
instruments at the route / service / model level; the template
renders them with the vertical-bands placeholder layout instead of
the standard Display / Response Fields tables.

See ``guide/instrument_builder_project.md`` for the concept the column tests.

Revision ID: b8f4e2a6c1d3
Revises: a7e3c5b1d9f8
Create Date: 2026-05-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8f4e2a6c1d3"
down_revision: Union[str, Sequence[str], None] = "a7e3c5b1d9f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "is_pilot",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.drop_column("is_pilot")
