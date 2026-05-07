"""Integration test for Segment 13A PR 3's seed-install migration.

Verifies that the migration installed exactly the five seeded
RuleSets from ``app/services/rules/seeds.py`` with the right shape
in the DB. Re-loads each row's ``rules_json`` through Pydantic and
asserts byte-equivalence with the in-memory definition.

This pins the migration's output against accidental seed-text
drift and catches the case where ``seeds.py`` evolves without a new
migration — the existing migration would silently produce different
output on a fresh DB but identical output on an existing one. The
test guards a fresh DB.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RuleSet, RuleSetRevision
from app.schemas.rules import Rule
from app.services.rules.seeds import SEEDS


def test_migration_installs_five_seeds(db: Session) -> None:
    rows = db.execute(
        select(RuleSet).where(RuleSet.is_seed.is_(True)).order_by(RuleSet.id)
    ).scalars().all()
    assert len(rows) == 5
    assert [row.name for row in rows] == [seed.name for seed in SEEDS]


def test_each_seed_has_exactly_one_revision_pointed_at(db: Session) -> None:
    rows = db.execute(
        select(RuleSet).where(RuleSet.is_seed.is_(True))
    ).scalars().all()
    for row in rows:
        revisions = db.execute(
            select(RuleSetRevision)
            .where(RuleSetRevision.rule_set_id == row.id)
            .order_by(RuleSetRevision.revision_no)
        ).scalars().all()
        assert len(revisions) == 1
        assert revisions[0].revision_no == 1
        assert row.current_revision_id == revisions[0].id


def test_each_seed_has_null_owner_and_no_deleted_at(db: Session) -> None:
    rows = db.execute(
        select(RuleSet).where(RuleSet.is_seed.is_(True))
    ).scalars().all()
    for row in rows:
        assert row.owner_user_id is None
        assert row.deleted_at is None
        assert row.scope == "seed"


def test_seed_rules_json_round_trips_through_pydantic(db: Session) -> None:
    """The JSON written by the migration must reload through the
    schema validators without drift. If a future seed addition
    breaks this, the failing test names the offending seed."""

    for seed in SEEDS:
        row = db.execute(
            select(RuleSet).where(RuleSet.name == seed.name)
        ).scalar_one()
        revision = db.execute(
            select(RuleSetRevision).where(
                RuleSetRevision.id == row.current_revision_id
            )
        ).scalar_one()

        assert revision.combinator == seed.combinator.value
        assert revision.exclude_self_reviews == seed.options.excludeSelfReviews
        assert revision.seed == seed.options.seed

        # Reload rules_json through the discriminated-union validator
        # and assert byte-equivalence with the in-memory seed.
        from pydantic import TypeAdapter

        rule_adapter = TypeAdapter(Rule)
        loaded_rules = [
            rule_adapter.validate_python(payload)
            for payload in revision.rules_json
        ]
        loaded_dump = [rule.model_dump(mode="json") for rule in loaded_rules]
        seed_dump = [rule.model_dump(mode="json") for rule in seed.rules]
        assert loaded_dump == seed_dump
