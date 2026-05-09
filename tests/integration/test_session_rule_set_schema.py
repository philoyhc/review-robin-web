"""Schema-level coverage for Segment 13D PR 2 — ``session_rule_sets``.

Pins the per-session snapshot-copy table contract for Segment 15C
to consume:

- Round-trip insert + read with both NULL and non-NULL
  ``library_origin_id``.
- ``ON DELETE SET NULL`` on ``library_origin_id`` clears the
  pointer when the referenced ``operator_rule_sets`` row is
  deleted (the session copy survives unchanged).
- ``ON DELETE CASCADE`` on ``session_id`` reaps the rows when the
  owning session is deleted.

The table sits inert until 15C wires the library / copy split;
this file is the schema gate.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    ReviewSession,
    RuleSet,
    SessionRuleSet,
    User,
)


def _make_user(db: Session, email: str) -> User:
    user = User(email=email, display_name=email.split("@", 1)[0])
    db.add(user)
    db.flush()
    return user


def _make_session(db: Session, code: str, owner: User | None = None) -> ReviewSession:
    if owner is None:
        owner = _make_user(db, f"op-{code}@example.edu")
    review_session = ReviewSession(
        name=code.title(), code=code, created_by_user_id=owner.id
    )
    db.add(review_session)
    db.flush()
    return review_session


def _make_library_rule_set(db: Session, owner: User, name: str) -> RuleSet:
    rs = RuleSet(
        name=name,
        scope="personal",
        owner_user_id=owner.id,
        is_seed=False,
    )
    db.add(rs)
    db.flush()
    return rs


def test_round_trip_with_library_origin(db: Session) -> None:
    """Snapshot-shaped insert with provenance pointer set."""

    owner = _make_user(db, "srs-rt@example.edu")
    review_session = _make_session(db, "srs-rt", owner=owner)
    library = _make_library_rule_set(db, owner, "My Personal RuleSet")

    row = SessionRuleSet(
        session_id=review_session.id,
        name="My Personal RuleSet (snapshot)",
        description="Auto-copied at session create.",
        combinator="ALL_OF",
        exclude_self_reviews=True,
        seed=None,
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
        library_origin_id=library.id,
    )
    db.add(row)
    db.flush()

    fetched = db.execute(
        select(SessionRuleSet).where(SessionRuleSet.id == row.id)
    ).scalar_one()
    assert fetched.session_id == review_session.id
    assert fetched.combinator == "ALL_OF"
    assert fetched.exclude_self_reviews is True
    assert fetched.library_origin_id == library.id
    assert fetched.library_origin is not None
    assert fetched.library_origin.id == library.id
    assert fetched.rules_json[0]["predicate"]["operator"] == "same_as"
    assert isinstance(fetched.created_at, datetime)


def test_round_trip_without_library_origin(db: Session) -> None:
    """Snapshot authored directly in the session — ``library_origin_id``
    NULL. Models the "+ New blank ruleset" path 15C exposes."""

    review_session = _make_session(db, "srs-orphan")
    db.add(
        SessionRuleSet(
            session_id=review_session.id,
            name="Inline draft",
            description="",
            combinator="ANY_OF",
            exclude_self_reviews=False,
            seed=42,
            rules_json=[],
            library_origin_id=None,
        )
    )
    db.flush()

    fetched = db.execute(
        select(SessionRuleSet).where(
            SessionRuleSet.session_id == review_session.id
        )
    ).scalar_one()
    assert fetched.library_origin_id is None
    assert fetched.library_origin is None
    assert fetched.seed == 42


def test_library_origin_set_null_on_library_delete(db: Session) -> None:
    """When the referenced ``operator_rule_sets`` row is deleted, the
    pointer on every session copy clears to NULL via SQL ``SET NULL``.
    The session copy survives unchanged."""

    owner = _make_user(db, "srs-setnull@example.edu")
    review_session = _make_session(db, "srs-setnull", owner=owner)
    library = _make_library_rule_set(db, owner, "Soon-to-be-deleted")

    snapshot = SessionRuleSet(
        session_id=review_session.id,
        name="Survives the library delete",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=True,
        rules_json=[],
        library_origin_id=library.id,
    )
    db.add(snapshot)
    db.flush()
    snapshot_id = snapshot.id

    db.delete(library)
    db.flush()
    db.expire_all()

    fetched = db.execute(
        select(SessionRuleSet).where(SessionRuleSet.id == snapshot_id)
    ).scalar_one()
    assert fetched.library_origin_id is None
    assert fetched.library_origin is None
    # Snapshot content + name preserved.
    assert fetched.name == "Survives the library delete"


def test_cascade_on_session_delete(db: Session) -> None:
    """Deleting the owning session reaps every snapshot row attached
    to it via ``ON DELETE CASCADE``."""

    review_session = _make_session(db, "srs-cascade")
    db.add(
        SessionRuleSet(
            session_id=review_session.id,
            name="Will die with the session",
            description="",
            combinator="ALL_OF",
            exclude_self_reviews=True,
            rules_json=[],
            library_origin_id=None,
        )
    )
    db.flush()
    session_id = review_session.id

    db.delete(review_session)
    db.flush()

    remaining = db.execute(
        select(SessionRuleSet).where(SessionRuleSet.session_id == session_id)
    ).scalars().all()
    assert remaining == []


def test_timestamp_columns_default_now(db: Session) -> None:
    """``created_at`` / ``updated_at`` carry the server-side default
    ``func.now()`` from ``TimestampMixin`` so callers don't have to
    pass them. Same convention as ``RuleSet`` / ``ReviewSession``."""

    review_session = _make_session(db, "srs-times")
    row = SessionRuleSet(
        session_id=review_session.id,
        name="Timestamp test",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=True,
        rules_json=[],
    )
    db.add(row)
    db.flush()
    db.refresh(row)

    assert row.created_at is not None
    assert row.updated_at is not None
    assert isinstance(row.created_at, datetime)
    assert isinstance(row.updated_at, datetime)
