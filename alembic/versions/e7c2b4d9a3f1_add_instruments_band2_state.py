"""add instruments.band2_state

Adds a nullable JSON column ``instruments.band2_state`` that
persists the operator's Band 2 selections + Band 3 response-field
definitions on the new-model instrument card. Shape:

    {
      "selected_display_keys": [
        "reviewee.name", "reviewee.tag_1", ...
      ],
      "response_fields": [
        {
          "name": "Rating",
          "data_type": "integer",
          "min": "1", "max": "5", "step": "",
          "list_options": "",
          "selected": true
        },
        ...
      ]
    }

Each entry in ``response_fields`` carries its own ``selected`` flag
(whether its paired pill is toggled into the preview row). Display
pill selection rides on ``selected_display_keys`` keyed by the
canonical ``<source_type>.<source_field>`` pill identifier.

Pure UX surface — the entries don't (yet) integrate with the real
``instrument_response_fields`` / ``response_type_definitions``
tables, so the reviewer surface still doesn't render response
inputs for new-model instruments. That integration is a separate
slice.

Revision ID: e7c2b4d9a3f1
Revises: d3b8e9a5f721
Create Date: 2026-05-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7c2b4d9a3f1"
down_revision: Union[str, Sequence[str], None] = "d3b8e9a5f721"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("band2_state", sa.JSON(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("instruments", schema=None) as batch_op:
        batch_op.drop_column("band2_state")
