"""instruments.self_reviews_active: the Self review toggle per instrument

Findings E3 (author's ruling, 2026-10-17): the Assignments page's
per-instrument **Self review** toggle was stored nowhere but in its rows'
``include``, so the next Prepare re-applied the session's
``self_reviews_active`` and undid it. The toggle now lives on the
instrument.

The upgrade adds the column ``NOT NULL`` with a ``TRUE`` server default,
then backfills each instrument whose session has self-reviews off to
``FALSE`` — what that session's next Prepare would have written. The
downgrade drops the column; the session's flag is untouched either way.

Revision ID: f3a7c1e9d5b2
Revises: e5c1a9d3b7f2
Create Date: 2026-10-17

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f3a7c1e9d5b2"
down_revision: Union[str, Sequence[str], None] = "e5c1a9d3b7f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.add_column(
            sa.Column(
                "self_reviews_active",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            )
        )
    instruments = sa.table(
        "instruments",
        sa.column("session_id", sa.Integer),
        sa.column("self_reviews_active", sa.Boolean),
    )
    sessions = sa.table(
        "sessions",
        sa.column("id", sa.Integer),
        sa.column("self_reviews_active", sa.Boolean),
    )
    op.execute(
        instruments.update()
        .where(
            instruments.c.session_id.in_(
                sa.select(sessions.c.id).where(
                    sessions.c.self_reviews_active.is_(sa.false())
                )
            )
        )
        .values(self_reviews_active=sa.false())
    )


def downgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.drop_column("self_reviews_active")
