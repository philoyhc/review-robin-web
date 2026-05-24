"""segment_18J wave 2 PR i — inline response-field bounds

Adds the inline-bound columns to ``instrument_response_fields``
that will replace the ``response_type_definitions`` FK lookup
for numerical + string types (Segment 18J Wave 2; see
``guide/new_model_instruments_outstanding.md`` Gap 6).

This is the **additive** slice. The new columns are populated by
a backfill from each row's existing RTD, but the ``response_type_id``
FK stays in place and all read paths continue to dereference it.
Subsequent PRs flip readers to the inline columns and drop the
FK + the seeded numerical / string RTDs.

New columns (all nullable; semantics depend on ``data_type``):

- ``data_type``        — duplicate of the RTD's data_type for the
                         post-FK-drop world.
- ``response_type``    — the RTD's name (e.g. "1-to-5int"). Carried
                         on the field so analytical exports preserve
                         the "ResponseType" column post-retirement.
- ``min`` / ``max``    — numeric bounds (and ``max`` doubles as
                         char-length cap for string types, matching
                         the RTD shape).
- ``step``             — increment for integer / decimal types.
- ``list_csv``         — comma-separated option list for list types.
                         For list types, the RTD itself survives
                         (Gap 6 keeps per-session List RTDs for
                         option-list reuse); the inline copy is for
                         the bridge-friendly post-retirement shape.

Backfill copies verbatim from the currently-pointed-at RTD. Zero
information loss; no rows orphaned.

Revision ID: f9c2d8a4b7e1
Revises: e7c2b4d9a3f1
Create Date: 2026-05-24
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f9c2d8a4b7e1"
down_revision: Union[str, Sequence[str], None] = "e7c2b4d9a3f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instrument_response_fields", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("data_type", sa.String(length=16), nullable=True)
        )
        batch_op.add_column(
            sa.Column("response_type", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(sa.Column("min", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("max", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("step", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("list_csv", sa.Text(), nullable=True))

    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE instrument_response_fields
            SET data_type = (
                    SELECT data_type FROM response_type_definitions
                    WHERE response_type_definitions.id =
                          instrument_response_fields.response_type_id
                ),
                response_type = (
                    SELECT response_type FROM response_type_definitions
                    WHERE response_type_definitions.id =
                          instrument_response_fields.response_type_id
                ),
                min = (
                    SELECT min FROM response_type_definitions
                    WHERE response_type_definitions.id =
                          instrument_response_fields.response_type_id
                ),
                max = (
                    SELECT max FROM response_type_definitions
                    WHERE response_type_definitions.id =
                          instrument_response_fields.response_type_id
                ),
                step = (
                    SELECT step FROM response_type_definitions
                    WHERE response_type_definitions.id =
                          instrument_response_fields.response_type_id
                ),
                list_csv = (
                    SELECT list_csv FROM response_type_definitions
                    WHERE response_type_definitions.id =
                          instrument_response_fields.response_type_id
                )
            """
        )
    )


def downgrade() -> None:
    with op.batch_alter_table("instrument_response_fields", schema=None) as batch_op:
        batch_op.drop_column("list_csv")
        batch_op.drop_column("step")
        batch_op.drop_column("max")
        batch_op.drop_column("min")
        batch_op.drop_column("response_type")
        batch_op.drop_column("data_type")
