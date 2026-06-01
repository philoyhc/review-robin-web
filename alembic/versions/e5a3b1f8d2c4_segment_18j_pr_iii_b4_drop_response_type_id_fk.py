"""segment_18J wave 2 PR iii-b4 — drop instrument_response_fields.response_type_id

After iii-b2 the seeded RTD set retired and post-iii-b3 the
operator RTD library retired too. Every numerical / string field
carries its bounds inline on ``instrument_response_fields``; the
remaining List-type fields can hold their option list inline via
``_inline_list_csv``. The ``response_type_id`` FK is no longer
a source of truth for anything and is dropped here.

The per-session ``response_type_definitions`` table itself
survives this PR — operators can still author standalone RTDs
via the per-instrument card, but they're no longer linked back
to any field. A follow-up PR (Wave 5) can retire the table + the
RTD card entirely.

Revision ID: e5a3b1f8d2c4
Revises: d4e1c8b5f372
Create Date: 2026-05-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5a3b1f8d2c4"
down_revision: Union[str, Sequence[str], None] = "d4e1c8b5f372"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table(
        "instrument_response_fields", schema=None
    ) as batch_op:
        # ``ix_irf_response_type_id`` is the explicit index name
        # given when the column was introduced (Segment 10D Slice 4a).
        batch_op.drop_index("ix_irf_response_type_id")
        batch_op.drop_constraint("fk_irf_response_type_id", type_="foreignkey")
        batch_op.drop_column("response_type_id")


def downgrade() -> None:
    # The FK + index get re-created with the *original* names
    # (``fk_irf_response_type_id`` + ``ix_irf_response_type_id``,
    # introduced by 8b3c1d4e5f7a) so 8b3c1d4e5f7a's downgrade
    # further back in the chain can drop them. Earlier versions
    # of this downgrade used different names — SQLite tolerates
    # the mismatch in batch-recreate mode, but Postgres's strict
    # DROP INDEX requires the original name.
    with op.batch_alter_table(
        "instrument_response_fields", schema=None
    ) as batch_op:
        batch_op.add_column(
            sa.Column(
                "response_type_id",
                sa.Integer(),
                nullable=True,
            )
        )
        batch_op.create_foreign_key(
            "fk_irf_response_type_id",
            "response_type_definitions",
            ["response_type_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_index(
            "ix_irf_response_type_id",
            ["response_type_id"],
        )
