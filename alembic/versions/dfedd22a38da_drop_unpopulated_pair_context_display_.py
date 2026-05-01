"""drop unpopulated pair_context display fields

Pure-DML migration. For every existing instrument, drops any
``pair_context_N`` display-field row whose corresponding
``pair_context_N`` slot is unpopulated across all assignments in
that instrument's session. Operator-typed labels on populated
slots are preserved.

Pair-context display fields are now seeded lazily by
``app.services.instruments.seed_display_fields_from_assignments``
when manual-assignment imports populate the slot — see
``guide/unfinished_business.md`` item #14. This migration removes
the stale rows that the previous unconditional default seed
created on every session.

Revision ID: dfedd22a38da
Revises: c2143bd329c7
Create Date: 2026-05-01 00:00:00.000000

"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "dfedd22a38da"
down_revision: Union[str, Sequence[str], None] = "c2143bd329c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _populated_slots_by_session(bind) -> dict[int, set[str]]:
    """Walk Assignment.context across all sessions and collect the set of
    populated pair_context slots per session_id. ``Assignment.context``
    is declared with SQLAlchemy's JSON type — Postgres stores it as
    JSONB and yields a dict via the driver; SQLite stores it as TEXT
    and yields the raw JSON string. Handle both."""
    populated: dict[int, set[str]] = {}
    rows = bind.execute(
        sa.text("SELECT session_id, context FROM assignments")
    ).fetchall()
    for session_id, context in rows:
        if not context:
            continue
        if isinstance(context, (bytes, bytearray)):
            context = context.decode("utf-8")
        if isinstance(context, str):
            try:
                context = json.loads(context)
            except (json.JSONDecodeError, ValueError):
                continue
        if not isinstance(context, dict):
            continue
        for slot in ("1", "2", "3"):
            value = context.get(f"pair_context_{slot}")
            if value:
                populated.setdefault(int(session_id), set()).add(slot)
    return populated


def upgrade() -> None:
    bind = op.get_bind()
    populated = _populated_slots_by_session(bind)

    candidate_rows = bind.execute(
        sa.text(
            "SELECT df.id, df.instrument_id, i.session_id, df.source_field "
            "FROM instrument_display_fields df "
            "JOIN instruments i ON i.id = df.instrument_id "
            "WHERE df.source_type = 'pair_context'"
        )
    ).fetchall()

    to_delete: list[int] = []
    affected_instrument_ids: set[int] = set()
    for df_id, instrument_id, session_id, source_field in candidate_rows:
        if source_field not in {"1", "2", "3"}:
            continue
        if source_field in populated.get(int(session_id), set()):
            continue
        to_delete.append(int(df_id))
        affected_instrument_ids.add(int(instrument_id))

    if to_delete:
        bind.execute(
            sa.text(
                "DELETE FROM instrument_display_fields WHERE id IN :ids"
            ).bindparams(sa.bindparam("ids", expanding=True)),
            {"ids": to_delete},
        )

    # Re-pack `order` to 0..N-1 for each affected instrument so deletions
    # don't leave gaps.
    for instrument_id in affected_instrument_ids:
        remaining = bind.execute(
            sa.text(
                "SELECT id FROM instrument_display_fields "
                "WHERE instrument_id = :iid "
                "ORDER BY \"order\", id"
            ),
            {"iid": instrument_id},
        ).fetchall()
        for new_order, (df_id,) in enumerate(remaining):
            bind.execute(
                sa.text(
                    "UPDATE instrument_display_fields "
                    "SET \"order\" = :new_order WHERE id = :df_id"
                ),
                {"new_order": new_order, "df_id": df_id},
            )


def downgrade() -> None:
    # No-op: this migration is data-cleanup only. Reseeding all three
    # pair_context rows on every instrument would conflict with the
    # post-c2143bd329c7 lazy-seed semantics; operators can re-add rows
    # manually via the Display Fields card.
    pass
