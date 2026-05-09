"""segment 13d pr6: instruments.group_kind

Adds the group-scoping flavour column for Segment 13C's
group-scoped instruments (one shared answer covers a whole group
of reviewees instead of per-reviewee). NULL = "regular
per-reviewee instrument" (current behaviour); 13C settles the
value-set.

Lands inert — no service module reads or writes the column;
reviewer-surface render behaviour unchanged. 13C PR 1 (now
collapsed into pure render path) reads it via the new render
adapter.

See ``guide/segment_13D_db_prep.md`` PR 6 and
``guide/segment_13C_enhanced_instrument.md``.

Revision ID: 38b72f14662c
Revises: 4efcf31d61d2
Create Date: 2026-05-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "38b72f14662c"
down_revision: Union[str, Sequence[str], None] = "4efcf31d61d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.add_column(
            sa.Column("group_kind", sa.String(length=32), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.drop_column("group_kind")
