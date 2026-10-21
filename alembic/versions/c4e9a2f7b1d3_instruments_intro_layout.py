"""instruments.intro_layout: which arrangement an instrument's intro takes

Segment 19Y Item 1 (``guide/archive/segment_19Y_more_ux_refinements.md``): each
instrument picks the layout of its intro on the reviewer surface.
``layout_1`` (the heading and help cards left, visibility right) is the
default, so every existing row takes it; ``layout_2`` is the earlier
arrangement. The upgrade adds the column ``NOT NULL`` with a server
default, which fills existing rows on SQLite and Postgres alike; the
downgrade drops it.

Revision ID: c4e9a2f7b1d3
Revises: e8b3c1d4f6a2
Create Date: 2026-10-20
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c4e9a2f7b1d3"
down_revision: Union[str, Sequence[str], None] = "e8b3c1d4f6a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.add_column(
            sa.Column(
                "intro_layout",
                sa.String(length=16),
                nullable=False,
                server_default="layout_1",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.drop_column("intro_layout")
