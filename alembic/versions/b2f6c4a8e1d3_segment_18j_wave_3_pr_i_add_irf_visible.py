"""segment_18J wave 3 PR i — add InstrumentResponseField.visible

Adds the ``visible`` column to ``instrument_response_fields`` so
the new-model card's Band 2 response-field pill (the chips after
the ``||`` divider) can dual-write its selected/deselected state
through to a real DB column — mirroring the
``InstrumentDisplayField.visible`` pattern that Gap 1 (Wave 1
PR #1395) put in place for display-field pills.

This is PR i of the three-PR Wave 3 ladder
(``guide/segment_18J_new_model_takeover.md``):

- **PR i (this one)** — additive schema + dual-write. The new
  column lands NOT NULL with default ``true`` so every existing
  row picks up the safe-by-default value. ``set_band2_state``
  starts dual-writing operator-authored JSON entries into real
  ``InstrumentResponseField`` rows via id-match; the chip's
  ``selected`` flag flips ``visible`` on the matched row.
  Reviewer-surface readers are untouched in this slice — they
  still pull the seeded ``DEFAULT_RESPONSE_FIELDS`` rows only.
- **PR ii** — flip readers + enforce required. Reviewer surface
  starts reading operator-authored rows where ``visible=true``.
- **PR iii** — retire the JSON write side; rows become the sole
  source of truth.

Revision ID: b2f6c4a8e1d3
Revises: e5a3b1f8d2c4
Create Date: 2026-05-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b2f6c4a8e1d3"
down_revision: Union[str, Sequence[str], None] = "e5a3b1f8d2c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch_alter_table for SQLite compatibility (table-rebuild
    # path). Add the column nullable first, backfill, then mark
    # NOT NULL so SQLite doesn't choke on a NOT-NULL-without-
    # default add against existing rows.
    #
    # ``server_default=sa.true()`` + the ``UPDATE ... SET visible
    # = true`` backfill use the portable Boolean literals;
    # SQLite tolerates ``1`` for booleans but Postgres rejects
    # ``DEFAULT 1`` / ``= 1`` with ``DatatypeMismatch`` /
    # ``operator does not exist: boolean = integer``.
    with op.batch_alter_table(
        "instrument_response_fields", schema=None
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "visible",
                sa.Boolean(),
                nullable=True,
                server_default=sa.true(),
            )
        )

    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE instrument_response_fields SET visible = true "
            "WHERE visible IS NULL"
        )
    )

    with op.batch_alter_table(
        "instrument_response_fields", schema=None
    ) as batch_op:
        batch_op.alter_column(
            "visible",
            existing_type=sa.Boolean(),
            nullable=False,
            server_default=None,
        )


def downgrade() -> None:
    with op.batch_alter_table(
        "instrument_response_fields", schema=None
    ) as batch_op:
        batch_op.drop_column("visible")
