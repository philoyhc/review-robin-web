"""seed locked Name / Email Display Fields rows on every instrument

Pure-DML migration. For every existing instrument that doesn't
already carry the two locked Display Fields rows
(``(reviewee, name)`` and ``(reviewee, email_or_identifier)``),
shift any existing display-field rows up by 2 and insert the
locked rows at orders 0 and 1.

Idempotent: skips instruments that already have both locked rows.
Slice 1 of Segment 10D — see ``guide/archive/segment_10D.md`` and
``spec/instruments.md`` for the spec.

Revision ID: 543aa71cd452
Revises: dfedd22a38da
Create Date: 2026-05-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "543aa71cd452"
down_revision: Union[str, Sequence[str], None] = "dfedd22a38da"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    instrument_ids = [
        row[0]
        for row in bind.execute(sa.text("SELECT id FROM instruments")).fetchall()
    ]
    for instrument_id in instrument_ids:
        existing = bind.execute(
            sa.text(
                "SELECT source_type, source_field "
                "FROM instrument_display_fields "
                "WHERE instrument_id = :iid"
            ),
            {"iid": instrument_id},
        ).fetchall()
        existing_pairs = {(st, sf) for st, sf in existing}

        has_name = ("reviewee", "name") in existing_pairs
        has_email = ("reviewee", "email_or_identifier") in existing_pairs
        if has_name and has_email:
            continue

        # Number of locked rows we're adding for this instrument (0–2).
        # Shift existing rows up by that count so the new rows can sit
        # at orders 0 and 1.
        shift = (0 if has_name else 1) + (0 if has_email else 1)
        if shift:
            bind.execute(
                sa.text(
                    "UPDATE instrument_display_fields "
                    "SET \"order\" = \"order\" + :shift "
                    "WHERE instrument_id = :iid"
                ),
                {"shift": shift, "iid": instrument_id},
            )

        if not has_name:
            bind.execute(
                sa.text(
                    "INSERT INTO instrument_display_fields "
                    "(instrument_id, source_type, source_field, label, "
                    "\"order\", visible) "
                    "VALUES (:iid, 'reviewee', 'name', '', 0, TRUE)"
                ),
                {"iid": instrument_id},
            )
        if not has_email:
            order_for_email = 1 if not has_name else 0
            bind.execute(
                sa.text(
                    "INSERT INTO instrument_display_fields "
                    "(instrument_id, source_type, source_field, label, "
                    "\"order\", visible) "
                    "VALUES (:iid, 'reviewee', 'email_or_identifier', '', "
                    ":ord, TRUE)"
                ),
                {"iid": instrument_id, "ord": order_for_email},
            )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM instrument_display_fields "
            "WHERE source_type = 'reviewee' "
            "AND source_field IN ('name', 'email_or_identifier')"
        )
    )
    # No order-shift back: any session that re-runs forward will repack
    # via ensure_locked_display_fields. Going through full cycles is
    # not destructive.
