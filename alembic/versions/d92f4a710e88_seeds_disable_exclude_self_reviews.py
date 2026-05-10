"""seeded RuleSets: flip exclude_self_reviews from true to false

The five seeded RuleSets installed by 9a7c2e1b4f60 originally shipped
with ``exclude_self_reviews = TRUE`` baked into their first revision.
That made self-reviews unreachable for any operator using a seed
without forking a Personal copy, so the default flips to ``FALSE``.

This migration only touches revisions belonging to seeded RuleSets
(``operator_rule_sets.is_seed = TRUE``); Personal forks and any
hand-edited revisions are left alone.

Idempotent — already-flipped rows are no-ops.

Revision ID: d92f4a710e88
Revises: 324a449e7856
Create Date: 2026-05-10 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d92f4a710e88"
down_revision: Union[str, Sequence[str], None] = "324a449e7856"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    operator_rule_sets = sa.table(
        "operator_rule_sets",
        sa.column("id", sa.Integer),
        sa.column("is_seed", sa.Boolean),
    )
    revisions = sa.table(
        "rule_set_revisions",
        sa.column("rule_set_id", sa.Integer),
        sa.column("exclude_self_reviews", sa.Boolean),
    )
    seed_ids = sa.select(operator_rule_sets.c.id).where(
        operator_rule_sets.c.is_seed.is_(True)
    )
    bind.execute(
        sa.update(revisions)
        .where(revisions.c.rule_set_id.in_(seed_ids))
        .values(exclude_self_reviews=False)
    )


def downgrade() -> None:
    bind = op.get_bind()
    operator_rule_sets = sa.table(
        "operator_rule_sets",
        sa.column("id", sa.Integer),
        sa.column("is_seed", sa.Boolean),
    )
    revisions = sa.table(
        "rule_set_revisions",
        sa.column("rule_set_id", sa.Integer),
        sa.column("exclude_self_reviews", sa.Boolean),
    )
    seed_ids = sa.select(operator_rule_sets.c.id).where(
        operator_rule_sets.c.is_seed.is_(True)
    )
    bind.execute(
        sa.update(revisions)
        .where(revisions.c.rule_set_id.in_(seed_ids))
        .values(exclude_self_reviews=True)
    )
