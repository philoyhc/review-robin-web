"""sessions.linked_app: the application a session is linked to

Segment 23E (``guide/segment_23E_linked_sessions.md``): a session another
application created through the handoff names it, so Review Robin can turn
off what that application does in its place. Nullable, no backfill: every
existing session is native. The downgrade drops it.

Revision ID: d4e7a2c9f1b3
Revises: c3f8a1d6e2b7
Create Date: 2026-11-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d4e7a2c9f1b3"
down_revision: str | Sequence[str] | None = "c3f8a1d6e2b7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("linked_app", sa.String(length=32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.drop_column("linked_app")
