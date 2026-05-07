"""segment 13a pr3: install seeded RuleSets

Hand-rolled data migration that installs the six canonical seeds
from ``app/services/rules/seeds.py`` into the ``rule_sets`` and
``rule_set_revisions`` tables (created by migration 8d57b772ffc4 in
PR 1).

The seeds are workspace-scoped — one row per seed, regardless of
how many sessions exist. Re-running this migration is prevented by
Alembic's revision tracking; the body itself doesn't guard against
double-insert because the framework already does.

Importing application code from a migration is normally a code
smell (the migration must remain replayable as the app evolves),
but in this case the trade-off is explicit: the seed definitions
stay close to the engine code (``app/services/rules/seeds.py``) so
edits to the canonical cases don't churn migration files. Future
seeds and seed edits ship as new appended migrations rather than
re-running this one.

Revision ID: 9a7c2e1b4f60
Revises: 8d57b772ffc4
Create Date: 2026-05-07 12:30:00.000000

"""
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9a7c2e1b4f60"
down_revision: Union[str, Sequence[str], None] = "8d57b772ffc4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Local import keeps the migration's dependency graph explicit and
    # avoids paying the import cost on chains that don't reach this
    # revision.
    from app.services.rules.seeds import SEEDS

    bind = op.get_bind()
    now = datetime.now(timezone.utc)

    # Lightweight column-typed table descriptors so SQLAlchemy's bind
    # processors handle Boolean / JSON correctly across SQLite and
    # Postgres. The full ORM models are too tightly coupled to current
    # app state for migration-time use.
    rule_sets = sa.table(
        "rule_sets",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("description", sa.Text),
        sa.column("scope", sa.String),
        sa.column("owner_user_id", sa.Integer),
        sa.column("is_seed", sa.Boolean),
        sa.column("current_revision_id", sa.Integer),
        sa.column("deleted_at", sa.DateTime),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    revisions = sa.table(
        "rule_set_revisions",
        sa.column("id", sa.Integer),
        sa.column("rule_set_id", sa.Integer),
        sa.column("revision_no", sa.Integer),
        sa.column("combinator", sa.String),
        sa.column("exclude_self_reviews", sa.Boolean),
        sa.column("seed", sa.Integer),
        sa.column("rules_json", sa.JSON),
        sa.column("created_at", sa.DateTime),
        sa.column("created_by_user_id", sa.Integer),
    )

    for seed in SEEDS:
        bind.execute(
            rule_sets.insert().values(
                name=seed.name,
                description=seed.description,
                scope="seed",
                owner_user_id=None,
                is_seed=True,
                current_revision_id=None,
                deleted_at=None,
                created_at=now,
                updated_at=now,
            )
        )
        rule_set_id = bind.execute(
            sa.select(rule_sets.c.id).where(
                sa.and_(
                    rule_sets.c.name == seed.name,
                    rule_sets.c.is_seed.is_(True),
                )
            )
        ).scalar_one()

        rules_payload = [rule.model_dump(mode="json") for rule in seed.rules]
        bind.execute(
            revisions.insert().values(
                rule_set_id=rule_set_id,
                revision_no=1,
                combinator=seed.combinator.value,
                exclude_self_reviews=seed.options.excludeSelfReviews,
                seed=seed.options.seed,
                rules_json=rules_payload,
                created_at=now,
                created_by_user_id=None,
            )
        )
        revision_id = bind.execute(
            sa.select(revisions.c.id).where(
                sa.and_(
                    revisions.c.rule_set_id == rule_set_id,
                    revisions.c.revision_no == 1,
                )
            )
        ).scalar_one()

        bind.execute(
            sa.update(rule_sets)
            .where(rule_sets.c.id == rule_set_id)
            .values(current_revision_id=revision_id)
        )


def downgrade() -> None:
    bind = op.get_bind()
    # Drop seed RuleSets and their revisions. The
    # ``ON DELETE CASCADE`` from ``rule_set_revisions.rule_set_id``
    # to ``rule_sets.id`` would normally chase children — but the
    # forward FK ``rule_sets.current_revision_id → rule_set_revisions.id``
    # blocks the parent delete in the wrong order. Null the pointer
    # first, then delete revisions, then delete rule_sets.
    rule_sets = sa.table(
        "rule_sets",
        sa.column("id", sa.Integer),
        sa.column("is_seed", sa.Boolean),
        sa.column("current_revision_id", sa.Integer),
    )
    revisions = sa.table(
        "rule_set_revisions",
        sa.column("rule_set_id", sa.Integer),
    )

    bind.execute(
        sa.update(rule_sets)
        .where(rule_sets.c.is_seed.is_(True))
        .values(current_revision_id=None)
    )
    seed_ids_subquery = sa.select(rule_sets.c.id).where(
        rule_sets.c.is_seed.is_(True)
    )
    bind.execute(
        sa.delete(revisions).where(
            revisions.c.rule_set_id.in_(seed_ids_subquery)
        )
    )
    bind.execute(
        sa.delete(rule_sets).where(rule_sets.c.is_seed.is_(True))
    )
