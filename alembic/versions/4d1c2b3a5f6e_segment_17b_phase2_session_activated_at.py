"""17b: add sessions.activated_at + backfill from audit

Stamps the moment a session was first activated
(``draft|validated → ready``). Lights up the **Start** column on
the reviewer lobby (17B Phase 2 PR A) and pre-positions for
Segment 18G's scheduled-activation work, which will fill the
same column with a planned open time pre-activation and let the
actual ``activated_at`` stamp take over once activation runs.

Lands as nullable so existing rows in any state are valid
without backfill. The upgrade then opportunistically backfills
``activated_at`` for already-``ready`` (or post-``ready``)
sessions from the earliest ``session.activated`` audit row — the
event was introduced long before 17B Phase 2, so historical
data is reachable. Sessions with no such audit row keep
``NULL`` (the lobby renders ``—`` for Start).

Revision ID: 4d1c2b3a5f6e
Revises: c3a9f1d7b2e8
Create Date: 2026-05-20

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "4d1c2b3a5f6e"
down_revision: Union[str, Sequence[str], None] = "c3a9f1d7b2e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Backfill from the earliest ``session.activated`` audit event
    # per session. ``audit_events`` carries the event's
    # ``created_at`` and the ``session_id`` — earliest row per
    # session gives the first-activation timestamp. Sessions
    # without any such row stay NULL.
    op.execute(
        sa.text(
            """
            UPDATE sessions
            SET activated_at = sub.first_activated_at
            FROM (
                SELECT session_id,
                       MIN(created_at) AS first_activated_at
                FROM audit_events
                WHERE event_type = 'session.activated'
                  AND session_id IS NOT NULL
                GROUP BY session_id
            ) AS sub
            WHERE sessions.id = sub.session_id
              AND sessions.activated_at IS NULL
            """
        )
    ) if op.get_bind().dialect.name == "postgresql" else op.execute(
        # SQLite doesn't accept the FROM-subquery UPDATE syntax;
        # use a correlated subquery instead. Functionally identical.
        sa.text(
            """
            UPDATE sessions
            SET activated_at = (
                SELECT MIN(audit_events.created_at)
                FROM audit_events
                WHERE audit_events.session_id = sessions.id
                  AND audit_events.event_type = 'session.activated'
            )
            WHERE sessions.activated_at IS NULL
            """
        )
    )


def downgrade() -> None:
    op.drop_column("sessions", "activated_at")
