"""reviewers / reviewees / observers: the directory account an address resolved to

Segment 21F rung 3 (``guide/segment_21F_directory_rosters.md``): a roster
address resolved through the directory at upload stores the account's
object ID, mail and UPN beside the address as written. All three are
nullable; an unresolved row has none. The object ID is indexed, since a
signed-in person's rows are found by it. No reader yet: rung 4 writes
the columns and rung 5 matches on them.

Revision ID: a7d3e9f1c2b5
Revises: c4e9a2f7b1d3
Create Date: 2026-10-31
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a7d3e9f1c2b5"
down_revision: Union[str, Sequence[str], None] = "c4e9a2f7b1d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("reviewers", "reviewees", "observers")


def upgrade() -> None:
    for table in _TABLES:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("directory_object_id", sa.String(length=64), nullable=True))
            batch.add_column(sa.Column("directory_mail", sa.String(length=320), nullable=True))
            batch.add_column(sa.Column("directory_upn", sa.String(length=320), nullable=True))
            batch.create_index(f"ix_{table}_directory_object_id", ["directory_object_id"])


def downgrade() -> None:
    for table in _TABLES:
        with op.batch_alter_table(table) as batch:
            batch.drop_index(f"ix_{table}_directory_object_id")
            batch.drop_column("directory_upn")
            batch.drop_column("directory_mail")
            batch.drop_column("directory_object_id")
