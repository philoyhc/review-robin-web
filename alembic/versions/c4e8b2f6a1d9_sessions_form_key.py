"""sessions.form_key: the secret key of the review form's page digest

Segment 19V Item 2 (``guide/segment_19V_public_id_revamp.md``): the
review form carries a digest of its page's assignment-ID set, so a post
against a page that changed since it rendered is refused. The digest is
keyed by this per-session secret, never rendered, so it reveals neither
the IDs nor their count. The upgrade adds the column nullable, backfills
a fresh random key per session, then makes it ``NOT NULL``. The
downgrade drops it.

Revision ID: c4e8b2f6a1d9
Revises: a9d4f2c7e1b8
Create Date: 2026-10-18

"""
import secrets
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c4e8b2f6a1d9"
down_revision: Union[str, Sequence[str], None] = "a9d4f2c7e1b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("form_key", sa.String(length=64), nullable=True))

    sessions = sa.table("sessions", sa.column("id", sa.Integer), sa.column("form_key", sa.String))
    conn = op.get_bind()
    for (session_id,) in conn.execute(sa.select(sessions.c.id)).all():
        conn.execute(
            sessions.update()
            .where(sessions.c.id == session_id)
            .values(form_key=secrets.token_hex(32))
        )

    with op.batch_alter_table("sessions") as batch:
        batch.alter_column("form_key", existing_type=sa.String(length=64), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.drop_column("form_key")
