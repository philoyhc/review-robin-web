"""19T Item 10: branching columns on response fields

Adds three nullable columns to ``instrument_response_fields``
(``guide/advanced_instruments.md`` Item 1, "Storage"):

- ``branch_parent_id`` — on a governed field, its parent field: a
  self-referencing foreign key, ``ON DELETE SET NULL``, indexed.
- ``branch_op`` — on a parent, the condition's operator token
  (``eq`` / ``ne`` / ``gt`` / ``ge`` / ``lt`` / ``le`` / ``is``).
- ``branch_value`` — on a parent, the condition's number, or List
  options comma-separated.

Lands inert: all nullable, no backfill, and nothing authors a branch
until the builder rung (``guide/segment_19T_odds_and_ends.md``
Item 10). The column is added without an inline FK and the named FK
and index attached in a second batch, since anonymous constraints
break SQLite batch mode (as in 499610263228); the downgrade drops the
FK by that name before the column, for ci-postgres's round trip.

Revision ID: 63b1bb107eb0
Revises: d8c31f7a6b40
Create Date: 2026-09-26

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "63b1bb107eb0"
down_revision: Union[str, Sequence[str], None] = "d8c31f7a6b40"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instrument_response_fields") as batch:
        batch.add_column(
            sa.Column("branch_parent_id", sa.Integer(), nullable=True)
        )
        batch.add_column(
            sa.Column("branch_op", sa.String(length=8), nullable=True)
        )
        batch.add_column(sa.Column("branch_value", sa.Text(), nullable=True))
    with op.batch_alter_table("instrument_response_fields") as batch:
        batch.create_foreign_key(
            "fk_instrument_response_fields_branch_parent_id",
            "instrument_response_fields",
            ["branch_parent_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(
            "ix_instrument_response_fields_branch_parent_id",
            ["branch_parent_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("instrument_response_fields") as batch:
        batch.drop_index("ix_instrument_response_fields_branch_parent_id")
        batch.drop_constraint(
            "fk_instrument_response_fields_branch_parent_id",
            type_="foreignkey",
        )
        batch.drop_column("branch_value")
        batch.drop_column("branch_op")
        batch.drop_column("branch_parent_id")
