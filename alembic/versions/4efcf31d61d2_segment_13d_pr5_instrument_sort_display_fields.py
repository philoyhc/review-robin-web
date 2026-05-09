"""segment 13d pr5: instruments.sort_display_fields

Adds the operator-defined default sort spec column for Segment
13B's per-instrument reviewer-surface sort. Each entry shapes
as ``{"source_type": str, "source_field": str, "direction":
"asc"|"desc"}``; NULL = "no operator default".

Lands inert — no service module reads or writes the column.
The reviewer surface keeps its current sort policy (instrument
order, then reviewee order). 13B's render-path slice consumes
it.

See ``guide/segment_13D_db_prep.md`` PR 5 and
``guide/segment_13B_sort_by_reviewee.md`` (originally PR 1, now
collapsed into 13B's render-path slice).

Revision ID: 4efcf31d61d2
Revises: 499610263228
Create Date: 2026-05-09

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "4efcf31d61d2"
down_revision: Union[str, Sequence[str], None] = "499610263228"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.add_column(
            sa.Column("sort_display_fields", sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.drop_column("sort_display_fields")
