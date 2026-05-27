"""segment 18m pr1: instruments.starts_new_page

Adds the per-instrument page-break flag for Segment 18M.
``true`` on this instrument means "page break exists between
this instrument and the one before it" — i.e. this instrument
starts a new page on the reviewer surface.

Backfill direction (locked decision 3): every existing
instrument backfills to ``TRUE`` so today's one-instrument-
per-page reviewer behaviour is visually unchanged on rollout.
The DB-level ``server_default`` is then flipped to ``FALSE``
so any future direct-SQL INSERT lines up with the model
default (new instruments created after this migration go on
the same page as their predecessor unless the operator opts
into a break). ORM creates always send an explicit value
via ``Instrument.starts_new_page`` (Mapped ``default=False``).

The flag is meaningful only for instruments at position ≥ 2
in the per-session order; the value on the first instrument
is ignored at render time. The migration backfills all rows
(including position-1) for simplicity — render-time ignores
the dead flag, so no per-row guard is needed.

Lands inert — no service or web code reads or writes the
column until 18M PR 1's service helpers
(``reorder_instruments`` + ``create_page_break_after`` +
``clear_page_break``) and PR 2's operator-UI wiring land.

Revision ID: e5c1a3b9d472
Revises: d2e4f6a8c1b3
Create Date: 2026-05-27

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5c1a3b9d472"
down_revision: Union[str, Sequence[str], None] = "d2e4f6a8c1b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.add_column(
            sa.Column(
                "starts_new_page",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
    # Flip the DB-level default to FALSE so future direct INSERTs
    # without an explicit value match the model default. The backfill
    # above already populated every existing row to TRUE.
    with op.batch_alter_table("instruments") as batch:
        batch.alter_column("starts_new_page", server_default=sa.false())


def downgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.drop_column("starts_new_page")
