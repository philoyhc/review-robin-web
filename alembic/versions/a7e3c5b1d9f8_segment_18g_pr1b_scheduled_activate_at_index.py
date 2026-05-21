"""segment 18g pr1b: index on sessions.scheduled_activate_at

Adds a B-tree index on ``sessions.scheduled_activate_at`` — the
column the lazy observer (Segment 18G Part 1) checks on every
session-related GET to find triggers whose fire moment has
passed. The per-session observer reads one row at a time today,
but a future cross-session sweep (e.g. cron-style or a worker)
will scan-many by value, and the index keeps that path
performant.

The column itself shipped inert in 18G PR 0a (revision
``e6d4a1c8b3f5``); this migration adds only the index.

Revision ID: a7e3c5b1d9f8
Revises: d5a8f2c4b7e9
Create Date: 2026-05-21

"""
from typing import Sequence, Union

from alembic import op


revision: str = "a7e3c5b1d9f8"
down_revision: Union[str, Sequence[str], None] = "d5a8f2c4b7e9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.create_index(
            "ix_sessions_scheduled_activate_at",
            ["scheduled_activate_at"],
        )


def downgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_index("ix_sessions_scheduled_activate_at")
