"""sessions.public_id: a random URL handle for each session

Segment 19V Item 1 (``guide/segment_19V_public_id_revamp.md``): session
URLs carry a random ``public_id`` instead of the auto-increment ``id``,
which counts the workspace. The upgrade adds the column nullable,
backfills every existing session with a fresh random value, then makes
it ``NOT NULL`` with a unique index. The downgrade drops the index and
the column.

Revision ID: a9d4f2c7e1b8
Revises: f3a7c1e9d5b2
Create Date: 2026-10-18

"""
import secrets
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a9d4f2c7e1b8"
down_revision: Union[str, Sequence[str], None] = "f3a7c1e9d5b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Frozen copy of the model's alphabet and length: a migration must not
# import app code that may change after it.
_ALPHABET = "23456789abcdefghjkmnpqrstuvwxyz"
_LENGTH = 10


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.add_column(sa.Column("public_id", sa.String(length=16), nullable=True))

    sessions = sa.table("sessions", sa.column("id", sa.Integer), sa.column("public_id", sa.String))
    conn = op.get_bind()
    used: set[str] = set()
    for (session_id,) in conn.execute(sa.select(sessions.c.id)).all():
        value = "".join(secrets.choice(_ALPHABET) for _ in range(_LENGTH))
        while value in used:
            value = "".join(secrets.choice(_ALPHABET) for _ in range(_LENGTH))
        used.add(value)
        conn.execute(
            sessions.update().where(sessions.c.id == session_id).values(public_id=value)
        )

    with op.batch_alter_table("sessions") as batch:
        batch.alter_column("public_id", existing_type=sa.String(length=16), nullable=False)
        batch.create_index("ix_sessions_public_id", ["public_id"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch:
        batch.drop_index("ix_sessions_public_id")
        batch.drop_column("public_id")
