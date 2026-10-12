"""What each participant is shown of their own roster entry (participant info)

Adds ``sessions.reviewer_self_fields``, ``sessions.reviewee_self_fields``
and ``sessions.observer_self_fields``: a JSON list of roster field keys
per participant, ``NULL`` meaning that participant's default
(`guide/participant_info.md`). One migration for all three (author,
2026-10-12); Item 1 reads and writes the reviewers' column only, so no
existing session changes what anyone sees.

Revision ID: c4a8e2f6d1b3
Revises: b7e3d91a4c62
Create Date: 2026-10-12

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c4a8e2f6d1b3"
down_revision: Union[str, Sequence[str], None] = "b7e3d91a4c62"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = ("reviewer_self_fields", "reviewee_self_fields", "observer_self_fields")


def upgrade() -> None:
    with op.batch_alter_table("sessions") as batch_op:
        for name in _COLUMNS:
            batch_op.add_column(sa.Column(name, sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("sessions") as batch_op:
        for name in reversed(_COLUMNS):
            batch_op.drop_column(name)
