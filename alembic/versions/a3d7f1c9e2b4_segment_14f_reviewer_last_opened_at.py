"""segment 14F rung 3d: reviewers.last_opened_at

When the reviewer last opened their review, through the session link or
a personal one. Feeds the Reviewer response metadata extract's
Timestamps chip (LastOpened). Nullable, no backfill: a reviewer who has
not opened since this lands reads empty.

Revision ID: a3d7f1c9e2b4
Revises: b7d4e2a9c1f3
Create Date: 2026-11-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3d7f1c9e2b4"
down_revision: str | Sequence[str] | None = "b7d4e2a9c1f3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("reviewers", schema=None) as batch_op:
        batch_op.add_column(sa.Column("last_opened_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("reviewers", schema=None) as batch_op:
        batch_op.drop_column("last_opened_at")
