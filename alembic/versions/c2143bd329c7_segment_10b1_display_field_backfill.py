"""segment 10b-1: backfill pair_context display fields on every instrument

Pure-DML migration. For every existing instrument, drops any
pair-context display-field rows under it and re-seeds three rows
(slots 1, 2, 3) with empty labels. Destructive within the
``(source_type='pair_context', source_field IN ('1','2','3'))``
filter — operator-typed labels on those slots are not preserved
across upgrade. Operator-added ``reviewee`` rows (Segment 10B-2) are
left untouched.

Revision ID: c2143bd329c7
Revises: 4e8a2b9c3d11
Create Date: 2026-04-30 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2143bd329c7"
down_revision: Union[str, Sequence[str], None] = "4e8a2b9c3d11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_PAIR_CONTEXT_SLOTS = (("1", 0), ("2", 1), ("3", 2))


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM instrument_display_fields "
            "WHERE source_type = 'pair_context' "
            "AND source_field IN ('1', '2', '3')"
        )
    )
    instrument_ids = [
        row[0]
        for row in bind.execute(sa.text("SELECT id FROM instruments")).fetchall()
    ]
    for instrument_id in instrument_ids:
        for source_field, order_index in _PAIR_CONTEXT_SLOTS:
            bind.execute(
                sa.text(
                    "INSERT INTO instrument_display_fields "
                    '(instrument_id, source_type, source_field, label, "order", visible) '
                    "VALUES (:instrument_id, 'pair_context', :source_field, '', :order_index, :visible)"
                ),
                {
                    "instrument_id": instrument_id,
                    "source_field": source_field,
                    "order_index": order_index,
                    "visible": True,
                },
            )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "DELETE FROM instrument_display_fields "
            "WHERE source_type = 'pair_context' "
            "AND source_field IN ('1', '2', '3')"
        )
    )
