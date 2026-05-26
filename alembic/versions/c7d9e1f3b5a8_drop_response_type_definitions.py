"""Drop response_type_definitions table

Retires the per-session ``response_type_definitions`` table.

Bounds + data_type live inline on ``instrument_response_fields``
since Wave 3 PR i (the six ``_inline_*`` columns); the FK
``response_type_id`` already dropped in Wave 3 PR iii-b4
(`e5a3b1f8d2c4`). The operator-facing Response Type Definitions
card on the Instruments page also retires in this PR.

Data preservation: every ``InstrumentResponseField`` row already
carries its own ``_inline_data_type`` / ``_inline_min`` /
``_inline_max`` / ``_inline_step`` / ``_inline_list_csv`` /
``_inline_response_type`` independently of the RTD row that
originally seeded them. Dropping the RTD table loses only the
RTD-side metadata (the named templates ``Long_text`` / ``Rating
1-5`` etc.); the per-field bounds survive intact.

Revision ID: c7d9e1f3b5a8
Revises: a3f7e2d1c9b5
Create Date: 2026-05-26
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c7d9e1f3b5a8"
down_revision: Union[str, Sequence[str], None] = "a3f7e2d1c9b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("response_type_definitions")


def downgrade() -> None:
    # Restore the table shape from the original Segment 10D Slice 4a
    # migration (``8b3c1d4e5f7a``). Seed rows do not get repopulated
    # — the seeded set was emptied in Wave 2 PR iii-b2.
    op.create_table(
        "response_type_definitions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("response_type", sa.String(length=64), nullable=False),
        sa.Column("data_type", sa.String(length=16), nullable=False),
        sa.Column("min", sa.Float(), nullable=True),
        sa.Column("max", sa.Float(), nullable=True),
        sa.Column("step", sa.Float(), nullable=True),
        sa.Column("list_csv", sa.Text(), nullable=True),
        sa.Column(
            "is_seeded", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "seed_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.UniqueConstraint(
            "session_id", "response_type", name="uq_rtd_session_name"
        ),
    )
