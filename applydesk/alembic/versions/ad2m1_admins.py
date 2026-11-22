"""AD2M: Admins

Revision ID: ad2m1admins
Revises: ad2w1firstsignin
Create Date: 2026-11-22

The Admin tier between Operator and the super-admin (segment AD2M,
`applydesk/spec/permissions.md` §2): `person.is_admin`, false for everyone
until the super-admin promotes someone.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ad2m1admins"
down_revision = "ad2w1firstsignin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "person",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    with op.batch_alter_table("person") as batch:
        batch.drop_column("is_admin")
