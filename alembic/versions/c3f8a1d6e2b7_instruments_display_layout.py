"""instruments.display_layout: where an instrument's display fields sit

Segment 20M (``guide/segment_20M_instruments_touch_up.md``): each
instrument picks how its display fields sit on the reviewer surface.
``across`` (a column per field) is today's layout and the default, so
every existing row takes it; ``stacked`` and ``joined`` put them under
the reviewee. The upgrade adds the column ``NOT NULL`` with a server
default, which fills existing rows on SQLite and Postgres alike; the
downgrade drops it.

Revision ID: c3f8a1d6e2b7
Revises: b9e2d4f7a1c6
Create Date: 2026-11-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3f8a1d6e2b7"
down_revision: str | Sequence[str] | None = "b9e2d4f7a1c6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.add_column(
            sa.Column(
                "display_layout",
                sa.String(length=16),
                nullable=False,
                server_default=sa.text("'across'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.drop_column("display_layout")
