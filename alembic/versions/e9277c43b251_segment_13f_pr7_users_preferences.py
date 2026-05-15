"""segment 13f pr7: users.preferences

Adds a nullable JSON column to ``users`` — a general
per-operator preferences container. The column holds a JSON
object whose keys are individual operator-level display
preferences.

First consumer: Segment 18B PR 2 reads / writes the
``display_timezone`` key (the operator's default timezone for
sessions they create). The container is deliberately general —
future operator-level display settings become new keys, not new
migrations. ``NULL`` (or an absent key) means "no preference
set"; the consumer falls through to its in-code default
(``UTC`` for the timezone key).

Lands inert — no service module reads or writes the column
until Segment 18B PR 2 lights it up.

See ``guide/segment_13F_more_db_prep.md`` PR 7 for the schema
rationale.

Revision ID: e9277c43b251
Revises: 2fec0f646bd2
Create Date: 2026-05-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e9277c43b251"
down_revision: Union[str, Sequence[str], None] = "2fec0f646bd2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("preferences", sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("preferences")
