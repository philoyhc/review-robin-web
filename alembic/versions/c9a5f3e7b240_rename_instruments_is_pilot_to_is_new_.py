"""rename instruments.is_pilot to is_new_model

Renames the Instrument Builder concept-test flag column from
``is_pilot`` to ``is_new_model`` to reflect the consolidated
naming. The column's shape, default, and nullability are
unchanged; only the name moves.

Revision ID: c9a5f3e7b240
Revises: b8f4e2a6c1d3
Create Date: 2026-05-23

"""
from typing import Sequence, Union

from alembic import op


revision: str = "c9a5f3e7b240"
down_revision: Union[str, Sequence[str], None] = "b8f4e2a6c1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.alter_column("is_pilot", new_column_name="is_new_model")


def downgrade() -> None:
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.alter_column("is_new_model", new_column_name="is_pilot")
