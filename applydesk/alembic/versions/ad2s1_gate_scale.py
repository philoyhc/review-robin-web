"""AD2S: a gate's response field as a scale

Revision ID: ad2s1gatescale
Revises: ad2l1emails
Create Date: 2026-11-25

A gate's response field answered as Review Robin's scale (segment AD2S,
`applydesk/guide/segment_AD2S_gate_scale.md`): `gate_field.scale`, false
for every field already kept, and `gate_field.scale_labels`, the
`start|middle|end` labels, "" for none. `type` stays the number type.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "ad2s1gatescale"
down_revision: str | Sequence[str] | None = "ad2l1emails"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("gate_field") as batch:
        batch.add_column(
            sa.Column("scale", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.add_column(
            sa.Column("scale_labels", sa.String(200), nullable=False, server_default="")
        )


def downgrade() -> None:
    with op.batch_alter_table("gate_field") as batch:
        batch.drop_column("scale_labels")
        batch.drop_column("scale")
