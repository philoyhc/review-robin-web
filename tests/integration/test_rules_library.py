"""Tests for ``app/services/rules/library.py`` — Segment 13A PR 4.

PR 4 ships seeds-only library; PR 5 extends with Personal RuleSets
owned by the operator. The query the library exposes is the same
one the editor's selector reads from, so coverage here also pins
the visibility model: seeds visible to all, Personal visible only
to the owner, soft-deleted hidden from the list (but
``load_rule_set`` still resolves them for audit refs).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import RuleSet, RuleSetRevision, User
from app.services.rules import library


def _make_user(db: Session, email: str) -> User:
    user = User(email=email, display_name=email.split("@", 1)[0])
    db.add(user)
    db.flush()
    return user


def _add_personal_rule_set(
    db: Session, *, owner: User, name: str
) -> RuleSet:
    rs = RuleSet(
        name=name,
        description="d",
        scope="personal",
        owner_user_id=owner.id,
        is_seed=False,
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
        created_by_user_id=owner.id,
    )
    db.add(rev)
    db.flush()
    rs.current_revision_id = rev.id
    db.flush()
    return rs


def test_list_visible_returns_five_seeds_when_no_personal_rows(
    db: Session,
) -> None:
    """Fresh DB ships the five seeds installed by Segment 13A PR 3."""

    alice = _make_user(db, "alice@example.edu")
    rule_sets = library.list_visible_rule_sets(db, user=alice)
    seed_names = [rs.name for rs in rule_sets if rs.is_seed]
    assert sorted(seed_names) == sorted(
        [
            "Cross-group peer review",
            "Full Matrix",
            "Intra-group peer review",
            "Same group, different role",
            "Three reviewers per reviewee",
        ]
    )


def test_list_visible_includes_owner_personal_rule_sets(db: Session) -> None:
    alice = _make_user(db, "alice@example.edu")
    bob = _make_user(db, "bob@example.edu")
    _add_personal_rule_set(db, owner=alice, name="Alice's custom")
    _add_personal_rule_set(db, owner=bob, name="Bob's custom")

    alice_visible = library.list_visible_rule_sets(db, user=alice)
    alice_personal = [rs for rs in alice_visible if not rs.is_seed]
    assert [rs.name for rs in alice_personal] == ["Alice's custom"]

    bob_visible = library.list_visible_rule_sets(db, user=bob)
    bob_personal = [rs for rs in bob_visible if not rs.is_seed]
    assert [rs.name for rs in bob_personal] == ["Bob's custom"]


def test_list_visible_hides_soft_deleted_personal_rule_sets(
    db: Session,
) -> None:
    alice = _make_user(db, "alice@example.edu")
    rs = _add_personal_rule_set(db, owner=alice, name="X")
    rs.deleted_at = datetime(2026, 5, 7, tzinfo=timezone.utc)
    db.flush()

    visible = library.list_visible_rule_sets(db, user=alice)
    assert "X" not in [r.name for r in visible]


def test_load_rule_set_resolves_soft_deleted_for_audit_refs(
    db: Session,
) -> None:
    """Past audit refs must still resolve even after the operator
    soft-deletes their RuleSet — the library list filter is the only
    surface that hides deleted rows."""

    alice = _make_user(db, "alice@example.edu")
    rs = _add_personal_rule_set(db, owner=alice, name="ToDelete")
    rs.deleted_at = datetime(2026, 5, 7, tzinfo=timezone.utc)
    db.flush()

    loaded = library.load_rule_set(db, rs.id)
    assert loaded is not None
    rule_set, revision = loaded
    assert rule_set.id == rs.id
    assert revision.revision_no == 1


def test_load_rule_set_returns_none_for_unknown_id(db: Session) -> None:
    assert library.load_rule_set(db, 999_999) is None
