"""users.unit

Segment 20D rung 5 (``guide/segment_20D_header_chrome.md``): an
operator's Unit, the top line of the bar on the sessions they create
(``docs/header_chrome.md`` §6). Nullable, at most 80 characters; NULL
means the workspace default. Only a system admin sets it.

Revision ID: c3e9a1f7d2b4
Revises: b2f8d4a6c1e9
Create Date: 2026-11-02
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c3e9a1f7d2b4"
down_revision: Union[str, Sequence[str], None] = "b2f8d4a6c1e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("unit", sa.String(length=80), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("unit")
