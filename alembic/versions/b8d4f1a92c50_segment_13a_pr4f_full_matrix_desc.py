"""segment 13a follow-up: trim Full Matrix seed description

The seed-install migration (9a7c2e1b4f60) imports seeds.py at run
time, so a fresh upgrade chain produces the new description. On
already-migrated environments the install migration ran once with
the old text — this fix-up migration brings the description in line
without re-running the installer.

Idempotent: the UPDATE is a no-op on rows that already carry the
new text.

Revision ID: b8d4f1a92c50
Revises: 9a7c2e1b4f60
Create Date: 2026-05-07 13:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b8d4f1a92c50"
down_revision: Union[str, Sequence[str], None] = "9a7c2e1b4f60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_NEW_DESCRIPTION = "Pair every reviewer with every reviewee."
_OLD_DESCRIPTION = (
    "Pair every reviewer with every reviewee. Equivalent to "
    "Simple mode's default."
)


def upgrade() -> None:
    rule_sets = sa.table(
        "rule_sets",
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("is_seed", sa.Boolean),
    )
    op.get_bind().execute(
        sa.update(rule_sets)
        .where(
            sa.and_(
                rule_sets.c.is_seed.is_(True),
                rule_sets.c.name == "Full Matrix",
            )
        )
        .values(description=_NEW_DESCRIPTION)
    )


def downgrade() -> None:
    rule_sets = sa.table(
        "rule_sets",
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("is_seed", sa.Boolean),
    )
    op.get_bind().execute(
        sa.update(rule_sets)
        .where(
            sa.and_(
                rule_sets.c.is_seed.is_(True),
                rule_sets.c.name == "Full Matrix",
            )
        )
        .values(description=_OLD_DESCRIPTION)
    )
