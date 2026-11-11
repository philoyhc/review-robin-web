"""instruments.response_layout: a column per response field, or stacked

Segment 20K (``guide/segment_20K_stacked_response_layout.md``): each
instrument picks how its response fields sit on the reviewer surface.
``columns`` (a column per field) is today's layout and the default, so
every existing row takes it; ``stacked`` puts the fields one per line in
a single cell. The upgrade adds the column ``NOT NULL`` with a server
default, which fills existing rows on SQLite and Postgres alike; the
downgrade drops it.

Revision ID: b9e2d4f7a1c6
Revises: a3d7f1c9e2b4
Create Date: 2026-11-11
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b9e2d4f7a1c6"
down_revision: str | Sequence[str] | None = "a3d7f1c9e2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.add_column(
            sa.Column(
                "response_layout",
                sa.String(length=16),
                nullable=False,
                server_default=sa.text("'columns'"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.drop_column("response_layout")
