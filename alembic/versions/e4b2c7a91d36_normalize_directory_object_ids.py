"""normalize stored directory object ids

Segment 20G rung 4 (``guide/segment_20G_directory_import_robustness.md``):
the roster rows' ``directory_object_id`` and ``users.external_principal_id``
are stored stripped and lower-cased (``email_identity.normalize_object_id``),
as every write now stores them, so matching compares plainly and the
indexes on those columns serve it rather than a ``lower(trim(...))`` scan.

Values that differ only by case or whitespace collapse to one; no unique
constraint covers these columns, so nothing collides. Downgrade is a
no-op: the original spelling is not kept, and a lower-cased GUID is the
same identity.

Revision ID: e4b2c7a91d36
Revises: c3e9a1f7d2b4
Create Date: 2026-11-03
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e4b2c7a91d36"
down_revision: str | Sequence[str] | None = "c3e9a1f7d2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

#: What Python's ``str.strip()`` removes from these ASCII values, as
#: ``users._by_email`` trims: SQL's one-argument ``trim`` strips spaces
#: only.
_WHITESPACE = " \t\n\r\f\v"

_COLUMNS = (
    ("reviewers", "directory_object_id"),
    ("reviewees", "directory_object_id"),
    ("observers", "directory_object_id"),
    ("users", "external_principal_id"),
)


def upgrade() -> None:
    for table, column in _COLUMNS:
        t = sa.table(table, sa.column(column, sa.String))
        c = t.c[column]
        normal = sa.func.lower(sa.func.trim(c, _WHITESPACE))
        op.execute(
            t.update().where(c.is_not(None)).where(c != normal).values({column: normal})
        )
        # A value that was only whitespace becomes NULL, as an unbound
        # row is stored.
        op.execute(t.update().where(c == "").values({column: None}))


def downgrade() -> None:
    # The original spelling is not kept; lower-case is the same identity.
    pass
