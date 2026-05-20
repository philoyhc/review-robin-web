"""segment 18g pr0c: sessions retention controls

Pre-positions two nullable columns on ``sessions`` for the
per-session retention overrides Segment 18G Part 4 (scheduled /
policy-driven purge) reads.

- ``retention_exception`` (Boolean, nullable) — opts a session
  out of any auto-purge entirely, e.g. for legal hold. ``NULL``
  and ``False`` both mean "no exception" (Part 4 normalises on
  read); only ``True`` opts out.
- ``retention_overrides`` (JSON, nullable) — overrides the
  deployment retention env-var defaults per-session
  (``response_days`` / ``audit_days`` / ``archived_days``
  integer keys) and also carries the per-session
  ``delete_after_archive`` ISO 8601 duration string (the
  auto-delete offset, anchored on the system-stamped archive
  timestamp). ``NULL`` means "use the deployment defaults".

Both columns inert at Part 0 — no service module reads or writes
them until 18G Part 4 lights them up. JSON shape validation
ships with the consumer Part.

See ``guide/segment_18G_scheduled_events.md`` Part 0c and
``spec/lifecycle.md`` §8 (the ``delete_after_archive`` offset
sits in this JSON because it's anchor-relative to the archive
event — no new anchor column needed).

Revision ID: d5a8f2c4b7e9
Revises: f2c7b9d3e8a4
Create Date: 2026-05-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "d5a8f2c4b7e9"
down_revision: Union[str, Sequence[str], None] = "f2c7b9d3e8a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("retention_exception", sa.Boolean(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("retention_overrides", sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_column("retention_overrides")
        batch_op.drop_column("retention_exception")
