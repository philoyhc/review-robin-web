"""segment 18g pr0b: sessions offset config columns

Pre-positions four nullable columns on ``sessions`` carrying the
anchor-relative offsets that drive Segment 18G's scheduled
events. Two JSON lists (events that fire on a sequence) and two
String singletons (events that fire once); all values are
ISO 8601 duration strings (e.g. ``-P1D``, ``-PT2H``, ``P30D``).

- ``invite_offsets`` — JSON list; anchor ``scheduled_activate_at``;
  consumer 18G Part 2 (auto-send invitations).
- ``reminder_offsets`` — JSON list; anchor ``deadline``;
  consumer 18G Part 5 (auto-send reminders).
- ``archive_offset`` — single ISO 8601 duration; anchor
  ``deadline``; default ``P30D`` (applied at the editor, not at
  the schema); consumer 18G Part 1 (auto-archive).
- ``release_until_offset`` — single ISO 8601 duration; anchor
  ``responses_release_at``; Participants-platform inert.

``String(16)`` sizes the singletons generously past the 10-day
max offset (e.g. ``-PT240H`` is 7 chars). All four columns
nullable and inert at Part 0 — no service module reads or writes
these until the consumer Part lights them up. The per-column
B-tree index, JSON shape validation, and editor default fill all
ship with the consumer Part, not here.

See ``guide/segment_18G_scheduled_events.md`` Part 0b and
``spec/lifecycle.md`` §8 (anchor table + the anchor-null
inertness rule).

Revision ID: f2c7b9d3e8a4
Revises: e6d4a1c8b3f5
Create Date: 2026-05-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f2c7b9d3e8a4"
down_revision: Union[str, Sequence[str], None] = "e6d4a1c8b3f5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("invite_offsets", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("reminder_offsets", sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column("archive_offset", sa.String(length=16), nullable=True)
        )
        batch_op.add_column(
            sa.Column("release_until_offset", sa.String(length=16), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_column("release_until_offset")
        batch_op.drop_column("archive_offset")
        batch_op.drop_column("reminder_offsets")
        batch_op.drop_column("invite_offsets")
