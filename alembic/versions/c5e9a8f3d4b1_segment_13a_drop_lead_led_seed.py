"""segment 13a follow-up: drop Lead-led review seed

Removes the Lead-led review seeded RuleSet from the library. The
seed convention (``tag2 = "Lead"``) is over-specific to a particular
workspace pattern, and operators who want OR-combinations / nested
composites can build them via the editor (Segment 13A PR 5+) once
that ships.

Engine coverage of ``ANY_OF`` / ``COMPOSITE`` / literal-``equals``
stays intact via ``tests/unit/test_rules_engine.py`` — those
primitives don't depend on this seed.

Idempotent: the DELETE is a no-op on databases that never had the
seed (e.g. fresh upgrades after this migration ships, where the
install migration's seeds.py import already excludes Lead-led).

Revision ID: c5e9a8f3d4b1
Revises: b8d4f1a92c50
Create Date: 2026-05-07 13:15:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c5e9a8f3d4b1"
down_revision: Union[str, Sequence[str], None] = "b8d4f1a92c50"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_SEED_NAME = "Lead-led review"


def upgrade() -> None:
    rule_sets = sa.table(
        "rule_sets",
        sa.column("id", sa.Integer),
        sa.column("name", sa.String),
        sa.column("is_seed", sa.Boolean),
        sa.column("current_revision_id", sa.Integer),
    )
    revisions = sa.table(
        "rule_set_revisions",
        sa.column("rule_set_id", sa.Integer),
    )
    bind = op.get_bind()

    # Mirror the install migration's downgrade order: NULL the forward
    # FK first to break the rule_sets ↔ rule_set_revisions cycle, then
    # delete revisions, then delete the rule_sets row itself.
    bind.execute(
        sa.update(rule_sets)
        .where(
            sa.and_(
                rule_sets.c.is_seed.is_(True),
                rule_sets.c.name == _SEED_NAME,
            )
        )
        .values(current_revision_id=None)
    )
    seed_id_subquery = sa.select(rule_sets.c.id).where(
        sa.and_(
            rule_sets.c.is_seed.is_(True),
            rule_sets.c.name == _SEED_NAME,
        )
    )
    bind.execute(
        sa.delete(revisions).where(
            revisions.c.rule_set_id.in_(seed_id_subquery)
        )
    )
    bind.execute(
        sa.delete(rule_sets).where(
            sa.and_(
                rule_sets.c.is_seed.is_(True),
                rule_sets.c.name == _SEED_NAME,
            )
        )
    )


def downgrade() -> None:
    # Re-create the Lead-led seed from the literal definition so a
    # downgrade restores the row a previous-version app expected to
    # find. The literal is inlined here (not imported from seeds.py)
    # because seeds.py no longer carries it; capturing the JSON shape
    # in the migration keeps the downgrade self-contained.
    from datetime import datetime, timezone

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

    bind = op.get_bind()
    now = datetime.now(timezone.utc)

    rules_payload = [
        {
            "id": "intra_group",
            "kind": "MATCH",
            "enabled": True,
            "predicate": {
                "field": "reviewer.tag1",
                "operator": "same_as",
                "operand": "reviewee.tag1",
                "case_sensitive": False,
            },
        },
        {
            "id": "cross_group_leads",
            "kind": "COMPOSITE",
            "enabled": True,
            "op": "AND",
            "rules": [
                {
                    "id": "rev_lead",
                    "kind": "MATCH",
                    "enabled": True,
                    "predicate": {
                        "field": "reviewer.tag2",
                        "operator": "equals",
                        "operand": "Lead",
                        "case_sensitive": False,
                    },
                },
                {
                    "id": "rvw_lead",
                    "kind": "MATCH",
                    "enabled": True,
                    "predicate": {
                        "field": "reviewee.tag2",
                        "operator": "equals",
                        "operand": "Lead",
                        "case_sensitive": False,
                    },
                },
                {
                    "id": "diff_tag1",
                    "kind": "MATCH",
                    "enabled": True,
                    "predicate": {
                        "field": "reviewer.tag1",
                        "operator": "different_from",
                        "operand": "reviewee.tag1",
                        "case_sensitive": False,
                    },
                },
            ],
        },
    ]

    bind.execute(
        rule_sets.insert().values(
            name=_SEED_NAME,
            description=(
                "Union of (a) intra-group pairings and (b) cross-group "
                "pairings where both sides have tag2 = Lead."
            ),
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
                rule_sets.c.is_seed.is_(True),
                rule_sets.c.name == _SEED_NAME,
            )
        )
    ).scalar_one()

    bind.execute(
        revisions.insert().values(
            rule_set_id=rule_set_id,
            revision_no=1,
            combinator="ANY_OF",
            exclude_self_reviews=True,
            seed=None,
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
