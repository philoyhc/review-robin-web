"""instruments (session_id, session_seq) unique

Segment 19V Item 3 (``guide/segment_19V_public_id_revamp.md``): the
observer's collation CSV is addressed by the instrument's per-session
``session_seq``, so no two instruments in a session may share one. The
column has been unconstrained since 19Q Item 6, so the upgrade first
renumbers any duplicate: in each session the lowest ``id`` keeps the
number and every other holder takes the next one past the session's
highest. Then it adds the unique constraint. The downgrade drops it and
leaves the numbers as they are.

Revision ID: d2f7a3c9b5e4
Revises: c4e8b2f6a1d9
Create Date: 2026-10-18

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d2f7a3c9b5e4"
down_revision: Union[str, Sequence[str], None] = "c4e8b2f6a1d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT = "uq_instruments_session_seq"


def renumber_duplicates(conn: sa.engine.Connection) -> None:
    """Give every duplicate ``session_seq`` a fresh number past its
    session's highest, keeping the lowest ``id``'s value."""
    instruments = sa.table(
        "instruments",
        sa.column("id", sa.Integer),
        sa.column("session_id", sa.Integer),
        sa.column("session_seq", sa.Integer),
    )
    rows = conn.execute(
        sa.select(
            instruments.c.id, instruments.c.session_id, instruments.c.session_seq
        ).order_by(instruments.c.session_id, instruments.c.id)
    ).all()
    highest: dict[int, int] = {}
    for _, session_id, seq in rows:
        highest[session_id] = max(highest.get(session_id, 0), seq)
    seen: set[tuple[int, int]] = set()
    for instrument_id, session_id, seq in rows:
        if (session_id, seq) not in seen:
            seen.add((session_id, seq))
            continue
        highest[session_id] += 1
        conn.execute(
            instruments.update()
            .where(instruments.c.id == instrument_id)
            .values(session_seq=highest[session_id])
        )


def upgrade() -> None:
    renumber_duplicates(op.get_bind())
    with op.batch_alter_table("instruments") as batch:
        batch.create_unique_constraint(_CONSTRAINT, ["session_id", "session_seq"])


def downgrade() -> None:
    with op.batch_alter_table("instruments") as batch:
        batch.drop_constraint(_CONSTRAINT, type_="unique")
