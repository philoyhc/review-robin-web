"""chip-controlled-drop PR 6 — data_shapes.include_empty_rows

Adds the per-shape empty-row drop chip state column to
``data_shapes``. Two valid values:

* ``True`` (default) — surface every relevant row, including
  rows whose accumulator is empty (today's behaviour; new
  default for backfill).
* ``False`` — drop rows whose ``_Acc.is_empty()`` from
  per-individual / per-tag-combo row schemes. Single-summary
  shapes always emit their one row regardless.

See the addendum on ``guide/self_review_consolidate.md``
"chip-controlled drop of empty rows on the Data shaper". Like
the sibling ``self_review_handling`` migration, no DB CHECK
constraint — the application gate (``include_empty_rows: bool``
in ``app/services/data_shapes.py``) is sufficient since the
column is a plain Boolean.

Revision ID: d8e4c3a1b5f6
Revises: c5d3f1a2b9e7
Create Date: 2026-05-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d8e4c3a1b5f6"
down_revision: Union[str, Sequence[str], None] = "c5d3f1a2b9e7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("data_shapes") as batch:
        batch.add_column(
            sa.Column(
                "include_empty_rows",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("data_shapes") as batch:
        batch.drop_column("include_empty_rows")
