"""segment 13f pr6: sessions.display_timezone

Adds a nullable per-session display-timezone column to
``sessions``. Holds an IANA zone name (e.g. ``Asia/Singapore``)
used to render the session's dates / times. ``NULL`` means
"inherit the creating operator's default timezone" — the
NULL-means-inherit semantics are load-bearing in Segment 18B's
resolution order (session override -> operator default -> UTC),
which is why the column is nullable rather than NOT NULL with a
default.

Lands inert — no service module reads or writes the column
until Segment 18B PR 3 lights it up (per-session timezone card
+ create-time stamping). Validity is enforced at the service
layer against ``zoneinfo.available_timezones()`` at light-up,
not by a DB CHECK constraint.

See ``guide/segment_13F_more_db_prep.md`` PR 6 for the schema
rationale.

Revision ID: 2fec0f646bd2
Revises: a4c8e91b2d6f
Create Date: 2026-05-15

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "2fec0f646bd2"
down_revision: Union[str, Sequence[str], None] = "a4c8e91b2d6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("display_timezone", sa.String(length=64), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("sessions", schema=None) as batch_op:
        batch_op.drop_column("display_timezone")
