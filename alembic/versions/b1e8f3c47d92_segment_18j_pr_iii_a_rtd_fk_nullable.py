"""segment_18J wave 2 PR iii-a — instrument_response_fields.response_type_id nullable

Smallest possible "open the door" slice of the RTD library
retirement (Gap 6). Makes the FK to ``response_type_definitions``
nullable so the iii-b cleanup can land NULL refs on numerical /
string fields before deleting the seeded non-List RTDs and
retiring the library tier.

After this migration:

- The column is nullable but every existing row still carries a
  non-NULL FK pointing at its RTD (no data change).
- The before_insert listener (PR i) still bridges the FK to the
  inline bound columns on new rows.
- The .response_type / .data_type properties still fall back to
  ``response_type_definition`` for any row whose inline columns
  are unset (defensive only — inline is populated for every row
  post-PR-i).

iii-b lands the seed deletion + creator-to-inline + library
tier retirement together.

Revision ID: b1e8f3c47d92
Revises: f9c2d8a4b7e1
Create Date: 2026-05-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1e8f3c47d92"
down_revision: Union[str, Sequence[str], None] = "f9c2d8a4b7e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table(
        "instrument_response_fields", schema=None
    ) as batch_op:
        batch_op.alter_column(
            "response_type_id",
            existing_type=sa.Integer(),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table(
        "instrument_response_fields", schema=None
    ) as batch_op:
        batch_op.alter_column(
            "response_type_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
