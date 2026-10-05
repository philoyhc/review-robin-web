"""Index the three unindexed data_shapes foreign keys (findings H2 / Hc4)

``docs/database.md`` "Indexes" states every ``ForeignKey`` column
declares ``index=True``. ``683e99cca6b7`` created ``data_shapes`` with
only ``session_id`` indexed, leaving ``instrument_id``,
``response_field_id`` and ``created_by_user_id`` bare. Each now gets the
plain B-tree index SQLAlchemy names for ``index=True``
(``ix_<table>_<column>``), so ``alembic check`` sees no drift against
the model.

Revision ID: e2503d04df0d
Revises: 14db60023e88
Create Date: 2026-10-05

"""
from typing import Sequence, Union

from alembic import op


revision: str = "e2503d04df0d"
down_revision: Union[str, Sequence[str], None] = "14db60023e88"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_COLUMNS = ("instrument_id", "response_field_id", "created_by_user_id")


def upgrade() -> None:
    for column in _COLUMNS:
        op.create_index(f"ix_data_shapes_{column}", "data_shapes", [column])


def downgrade() -> None:
    for column in reversed(_COLUMNS):
        op.drop_index(f"ix_data_shapes_{column}", table_name="data_shapes")
