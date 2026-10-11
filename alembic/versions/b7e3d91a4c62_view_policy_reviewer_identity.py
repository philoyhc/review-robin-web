"""How much of a reviewer a Raw released view identifies (ProfileLink Item 2)

Adds ``instrument_view_policies.after_release_reviewer_identity``: on a
reviewee or observer row whose released cell is Raw, the reviewer reads
as ``name``, ``name_email`` or ``name_email_profile``
(`guide/profilelink_updates.md` Item 2). ``NULL`` means ``name_email``,
which is what Raw showed before, so no existing row changes.

Revision ID: b7e3d91a4c62
Revises: 4cc450a87931
Create Date: 2026-10-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b7e3d91a4c62"
down_revision: Union[str, Sequence[str], None] = "4cc450a87931"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("instrument_view_policies") as batch_op:
        batch_op.add_column(
            sa.Column(
                "after_release_reviewer_identity",
                sa.String(length=24),
                nullable=True,
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("instrument_view_policies") as batch_op:
        batch_op.drop_column("after_release_reviewer_identity")
