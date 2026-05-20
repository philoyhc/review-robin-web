"""segment 18g pr0a: sessions anchor datetime columns

Pre-positions two nullable ``DateTime(timezone=True)`` columns on
``sessions`` — the **anchor** datetimes Segment 18G's Part 0b
offsets are computed against.

- ``scheduled_activate_at`` — the operator-set trigger for the
  scheduled ``validated → ready`` transition (consumer: 18G
  Part 3). Distinct from the existing ``activated_at`` (system-
  stamped record of when activation actually fired).
- ``responses_release_at`` — the Participants-platform
  "reviewees can view responses from this point" anchor;
  pre-positioned inert so future participant-model work needs no
  follow-on migration. No 18G Part reads it.

Both nullable, both inert. No service module reads or writes
these until the consumer Part lights them up. The per-column
B-tree index is deferred to the owning consumer Part.

See ``guide/segment_18G_scheduled_events.md`` Part 0a and
``spec/lifecycle.md`` §8 for the model.

Revision ID: e6d4a1c8b3f5
Revises: 4d1c2b3a5f6e
Create Date: 2026-05-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e6d4a1c8b3f5"
down_revision: Union[str, Sequence[str], None] = "4d1c2b3a5f6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "scheduled_activate_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "responses_release_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_column("responses_release_at")
        batch_op.drop_column("scheduled_activate_at")
