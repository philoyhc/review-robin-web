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
    import json

    from app.services.rules.seeds import SEEDS

    bind = op.get_bind()
    now = datetime.now(timezone.utc)

    for seed in SEEDS:
        bind.execute(
            sa.text(
                "INSERT INTO rule_sets "
                "(name, description, scope, owner_user_id, is_seed, "
                " current_revision_id, deleted_at, created_at, updated_at) "
                "VALUES (:name, :description, 'seed', NULL, 1, "
                "        NULL, NULL, :now, :now)"
            ),
            {"name": seed.name, "description": seed.description, "now": now},
        )
        rule_set_id = bind.execute(
            sa.text(
                "SELECT id FROM rule_sets "
                "WHERE name = :name AND is_seed = 1"
            ),
            {"name": seed.name},
        ).scalar_one()

        rules_payload = [rule.model_dump(mode="json") for rule in seed.rules]
        bind.execute(
            sa.text(
                "INSERT INTO rule_set_revisions "
                "(rule_set_id, revision_no, combinator, "
                " exclude_self_reviews, seed, rules_json, "
                " created_at, created_by_user_id) "
                "VALUES (:rule_set_id, 1, :combinator, "
                "        :exclude_self_reviews, :seed, :rules_json, "
                "        :now, NULL)"
            ),
            {
                "rule_set_id": rule_set_id,
                "combinator": seed.combinator.value,
                "exclude_self_reviews": seed.options.excludeSelfReviews,
                "seed": seed.options.seed,
                # Both SQLite (TEXT-encoded) and Postgres (JSONB-encoded)
                # accept a JSON-string blob through the JSON type adapter,
                # but going through ``json.dumps`` keeps the column
                # contents identical across dialects.
                "rules_json": json.dumps(rules_payload),
                "now": now,
            },
        )
        revision_id = bind.execute(
            sa.text(
                "SELECT id FROM rule_set_revisions "
                "WHERE rule_set_id = :rule_set_id AND revision_no = 1"
            ),
            {"rule_set_id": rule_set_id},
        ).scalar_one()

        bind.execute(
            sa.text(
                "UPDATE rule_sets SET current_revision_id = :rev "
                "WHERE id = :rs"
            ),
            {"rev": revision_id, "rs": rule_set_id},
        )


def downgrade() -> None:
    bind = op.get_bind()
    # Drop seed RuleSets and their revisions. The
    # ``ON DELETE CASCADE`` from ``rule_set_revisions.rule_set_id``
    # to ``rule_sets.id`` would normally chase children — but the
    # forward FK ``rule_sets.current_revision_id → rule_set_revisions.id``
    # blocks the parent delete in the wrong order. Null the pointer
    # first, then delete revisions, then delete rule_sets.
    bind.execute(
        sa.text(
            "UPDATE rule_sets SET current_revision_id = NULL "
            "WHERE is_seed = 1"
        )
    )
    bind.execute(
        sa.text(
            "DELETE FROM rule_set_revisions WHERE rule_set_id IN "
            "(SELECT id FROM rule_sets WHERE is_seed = 1)"
        )
    )
    bind.execute(sa.text("DELETE FROM rule_sets WHERE is_seed = 1"))
