"""Schema-level coverage for Segment 13A PR 1 — ``rule_sets`` and
``rule_set_revisions``.

PR 1 lands the persistence layer only; PR 2 wires the engine and
PR 3 inserts the seeded RuleSets. This file pins the table contract
for the engine and the seed installer to consume.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RuleSet, RuleSetRevision, User


def _make_user(db: Session, email: str) -> User:
    user = User(email=email, display_name=email.split("@", 1)[0])
    db.add(user)
    db.flush()
    return user


def test_rule_set_persists_with_first_revision(db: Session) -> None:
    """A Personal-scope RuleSet with one revision round-trips through
    the ORM; ``current_revision_id`` points at the inserted revision."""

    owner = _make_user(db, "alice@example.edu")
    rs = RuleSet(
        name="Alice's intra-group",
        description="Tag1 same",
        scope="personal",
        owner_user_id=owner.id,
        is_seed=False,
    )
    db.add(rs)
    db.flush()

    revision = RuleSetRevision(
        rule_set_id=rs.id,
        revision_no=1,
        combinator="ALL_OF",
        exclude_self_reviews=True,
        rules_json=[
            {
                "id": "same_group",
                "kind": "MATCH",
                "enabled": True,
                "predicate": {
                    "field": "reviewer.tag1",
                    "operator": "same_as",
                    "operand": "reviewee.tag1",
                    "case_sensitive": False,
                },
            }
        ],
        created_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
        created_by_user_id=owner.id,
    )
    db.add(revision)
    db.flush()
    rs.current_revision_id = revision.id
    db.flush()

    fetched = db.execute(
        select(RuleSet).where(RuleSet.id == rs.id)
    ).scalar_one()
    assert fetched.scope == "personal"
    assert fetched.owner_user_id == owner.id
    assert fetched.current_revision_id == revision.id
    assert fetched.deleted_at is None
    assert fetched.current_revision is not None
    assert fetched.current_revision.combinator == "ALL_OF"
    assert (
        fetched.current_revision.rules_json[0]["predicate"]["operator"]
        == "same_as"
    )


def test_rule_set_seed_has_null_owner(db: Session) -> None:
    """Seed RuleSets carry no owner; the FK is nullable for that
    case. Uses a sentinel name so it doesn't collide with the
    canonical seeds installed by Segment 13A PR 3's migration."""

    rs = RuleSet(
        name="__test_seed__",
        description="Sentinel seed for the null-owner test.",
        scope="seed",
        owner_user_id=None,
        is_seed=True,
    )
    db.add(rs)
    db.flush()

    revision = RuleSetRevision(
        rule_set_id=rs.id,
        revision_no=1,
        combinator="ALL_OF",
        exclude_self_reviews=True,
        rules_json=[],
        created_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
        created_by_user_id=None,
    )
    db.add(revision)
    db.flush()
    rs.current_revision_id = revision.id
    db.flush()

    fetched = db.execute(
        select(RuleSet).where(RuleSet.name == "__test_seed__")
    ).scalar_one()
    assert fetched.owner_user_id is None
    assert fetched.current_revision.rules_json == []


def test_rule_set_revisions_unique_per_revision_no(db: Session) -> None:
    """The ``(rule_set_id, revision_no)`` pair is unique — two revs
    with the same number on the same RuleSet violate the constraint."""

    owner = _make_user(db, "bob@example.edu")
    rs = RuleSet(
        name="rs",
        scope="personal",
        owner_user_id=owner.id,
        is_seed=False,
    )
    db.add(rs)
    db.flush()

    db.add(
        RuleSetRevision(
            rule_set_id=rs.id,
            revision_no=1,
            combinator="ALL_OF",
            exclude_self_reviews=True,
            rules_json=[],
            created_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
        )
    )
    db.flush()

    db.add(
        RuleSetRevision(
            rule_set_id=rs.id,
            revision_no=1,
            combinator="ANY_OF",
            exclude_self_reviews=False,
            rules_json=[],
            created_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
        )
    )
    import pytest
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        db.flush()


def test_rule_set_cascade_deletes_revisions(db: Session) -> None:
    """Hard-deleting a RuleSet cascades through to its revisions
    (FK ``ON DELETE CASCADE``). Soft delete via ``deleted_at`` is the
    operator-facing path; this test pins the FK behaviour for any
    admin / migration-time hard delete."""

    owner = _make_user(db, "carol@example.edu")
    rs = RuleSet(
        name="rs", scope="personal", owner_user_id=owner.id, is_seed=False
    )
    db.add(rs)
    db.flush()
    rev = RuleSetRevision(
        rule_set_id=rs.id,
        revision_no=1,
        combinator="ALL_OF",
        exclude_self_reviews=True,
        rules_json=[],
        created_at=datetime(2026, 5, 7, tzinfo=timezone.utc),
    )
    db.add(rev)
    db.flush()
    rev_id = rev.id
    rs.current_revision_id = None
    db.flush()

    db.delete(rs)
    db.flush()

    assert (
        db.execute(
            select(RuleSetRevision).where(RuleSetRevision.id == rev_id)
        ).scalar_one_or_none()
        is None
    )
