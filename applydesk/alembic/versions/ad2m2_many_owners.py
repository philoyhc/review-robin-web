"""AD2M: more than one Owner

Revision ID: ad2m2manyowners
Revises: ad2m1admins
Create Date: 2026-11-22

An exercise may have more than one Owner (segment AD2M: adopting makes an
Admin or the super-admin an Owner beside the others,
`applydesk/spec/permissions.md` §3). The one-Owner index goes; the
exercise's row lock keeps changes to its Owners one at a time. A downgrade
puts the index back, which fails while any exercise has two Owners.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ad2m2manyowners"
down_revision = "ad2m1admins"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("uq_exercise_one_owner", table_name="exercise_operator")


def downgrade() -> None:
    op.create_index(
        "uq_exercise_one_owner",
        "exercise_operator",
        ["exercise_id"],
        unique=True,
        sqlite_where=sa.text("is_owner"),
        postgresql_where=sa.text("is_owner"),
    )
