"""instruments.session_seq — the per-session instrument number

Segment 19Q Item 6. The operator-facing instrument number was
``Instrument.id``, a workspace-wide autoincrement, so two instruments
in one session could be labelled ``Instrument_1`` and ``Instrument_7``.
This column carries a per-session number instead, assigned once at
creation and never updated.

**Not ``order``**: instrument drag-and-drop ships, and a number that
moved under the drag is the defect being removed. ``session_seq`` is
creation order and is independent of display order.

Backfill: rank each row among its session's rows by ``id`` ascending,
which is creation order, via a correlated ``COUNT`` rather than a
window function. ``ROW_NUMBER() OVER (...)`` would need ``UPDATE ...
FROM`` to land the result, and that is Postgres syntax SQLite only
gained in 3.33 — the correlated form is plain SQL-92 and runs the same
on both. Existing rows therefore come out contiguous (1..n per
session); gaps only appear once an operator deletes.

Added nullable, backfilled, then made ``NOT NULL`` — the column
deliberately carries no server default, so a creation path that forgets
it fails loudly instead of minting ``Instrument_0``.

Revision ID: b7d4f2a9c153
Revises: a3f1c7e9b204
Create Date: 2026-09-19

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b7d4f2a9c153"
down_revision: Union[str, Sequence[str], None] = "a3f1c7e9b204"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BACKFILL = sa.text(
    """
    UPDATE instruments
    SET session_seq = (
        SELECT COUNT(*)
        FROM instruments AS earlier
        WHERE earlier.session_id = instruments.session_id
          AND earlier.id <= instruments.id
    )
    """
)


def upgrade() -> None:
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("session_seq", sa.Integer(), nullable=True)
        )

    op.get_bind().execute(_BACKFILL)

    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.alter_column(
            "session_seq", existing_type=sa.Integer(), nullable=False
        )


def downgrade() -> None:
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.drop_column("session_seq")
