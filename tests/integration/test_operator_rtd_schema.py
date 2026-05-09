"""Schema-level coverage for Segment 13D PR 3 — operator-library
tier for RTDs (``operator_response_type_definitions``) plus the
provenance column on the existing per-session
``response_type_definitions`` table.

Pins the table contract for Segment 15C to consume:

- Round-trip insert + read on the operator-library table.
- ``UNIQUE (owner_user_id, response_type)`` enforced.
- ``ON DELETE CASCADE`` on ``owner_user_id`` reaps library rows
  when the owning user is deleted.
- ``response_type_definitions.library_origin_id`` round-trips
  with NULL + non-NULL values.
- ``ON DELETE SET NULL`` on ``library_origin_id`` clears the
  pointer when the referenced library row is deleted; the
  per-session RTD survives unchanged.

Both shapes sit inert until 15C wires the library / copy split.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    OperatorResponseTypeDefinition,
    ResponseTypeDefinition,
    ReviewSession,
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


def test_operator_rtd_round_trip(db: Session) -> None:
    """Insert + read; library row carries the canonical RTD shape."""

    owner = _make_user(db, "ortd-rt@example.edu")
    row = OperatorResponseTypeDefinition(
        owner_user_id=owner.id,
        response_type="Likert7",
        data_type="int",
        min=1.0,
        max=7.0,
        step=1.0,
    )
    db.add(row)
    db.flush()

    fetched = db.execute(
        select(OperatorResponseTypeDefinition).where(
            OperatorResponseTypeDefinition.id == row.id
        )
    ).scalar_one()
    assert fetched.owner_user_id == owner.id
    assert fetched.response_type == "Likert7"
    assert fetched.data_type == "int"
    assert fetched.min == 1.0
    assert fetched.max == 7.0
    assert fetched.step == 1.0
    assert fetched.list_csv is None


def test_operator_rtd_unique_per_owner_name(db: Session) -> None:
    """Two library rows with the same (owner, response_type) tuple
    violate ``uq_operator_rtd_owner_name``."""

    owner = _make_user(db, "ortd-uq@example.edu")
    db.add(
        OperatorResponseTypeDefinition(
            owner_user_id=owner.id,
            response_type="Custom",
            data_type="int",
            min=0.0,
            max=10.0,
        )
    )
    db.flush()

    db.add(
        OperatorResponseTypeDefinition(
            owner_user_id=owner.id,
            response_type="Custom",
            data_type="decimal",
            min=0.0,
            max=1.0,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_same_response_type_different_owners_ok(db: Session) -> None:
    """Two operators can each have a "Likert5" in their library."""

    alice = _make_user(db, "alice-ortd@example.edu")
    bob = _make_user(db, "bob-ortd@example.edu")
    db.add(
        OperatorResponseTypeDefinition(
            owner_user_id=alice.id,
            response_type="Likert5",
            data_type="int",
            min=1.0,
            max=5.0,
            step=1.0,
        )
    )
    db.add(
        OperatorResponseTypeDefinition(
            owner_user_id=bob.id,
            response_type="Likert5",
            data_type="list",
            list_csv="Strongly agree,Agree,Neutral,Disagree,Strongly disagree",
        )
    )
    db.flush()

    rows = db.execute(
        select(OperatorResponseTypeDefinition).where(
            OperatorResponseTypeDefinition.response_type == "Likert5"
        )
    ).scalars().all()
    assert len(rows) == 2
    assert {r.owner_user_id for r in rows} == {alice.id, bob.id}


def test_cascade_on_user_delete(db: Session) -> None:
    """Deleting the owning user reaps every library row attached to
    them via ``ON DELETE CASCADE``."""

    owner = _make_user(db, "ortd-cascade@example.edu")
    db.add(
        OperatorResponseTypeDefinition(
            owner_user_id=owner.id,
            response_type="ToBeDeleted",
            data_type="int",
            min=0.0,
            max=10.0,
        )
    )
    db.flush()
    owner_id = owner.id

    db.delete(owner)
    db.flush()

    remaining = db.execute(
        select(OperatorResponseTypeDefinition).where(
            OperatorResponseTypeDefinition.owner_user_id == owner_id
        )
    ).scalars().all()
    assert remaining == []


def test_response_type_definition_library_origin_round_trip(
    db: Session,
) -> None:
    """The new ``library_origin_id`` column on the per-session table
    accepts both NULL (no library origin) and non-NULL (copied from
    a library row) values."""

    owner = _make_user(db, "rtd-prov@example.edu")
    review_session = _make_session(db, "rtd-prov", owner=owner)
    library = OperatorResponseTypeDefinition(
        owner_user_id=owner.id,
        response_type="Likert5",
        data_type="int",
        min=1.0,
        max=5.0,
        step=1.0,
    )
    db.add(library)
    db.flush()

    with_origin = ResponseTypeDefinition(
        session_id=review_session.id,
        response_type="Likert5",
        data_type="int",
        min=1.0,
        max=5.0,
        step=1.0,
        is_seeded=False,
        library_origin_id=library.id,
    )
    without_origin = ResponseTypeDefinition(
        session_id=review_session.id,
        response_type="Inline",
        data_type="long_text",
        is_seeded=False,
        library_origin_id=None,
    )
    db.add_all([with_origin, without_origin])
    db.flush()

    fetched_with = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.id == with_origin.id
        )
    ).scalar_one()
    fetched_without = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.id == without_origin.id
        )
    ).scalar_one()
    assert fetched_with.library_origin_id == library.id
    assert fetched_without.library_origin_id is None


def test_library_origin_set_null_on_library_delete(db: Session) -> None:
    """When the referenced ``operator_response_type_definitions`` row
    is deleted, the pointer on every per-session RTD clears via SQL
    ``SET NULL``. The per-session RTD survives unchanged."""

    owner = _make_user(db, "rtd-setnull@example.edu")
    review_session = _make_session(db, "rtd-setnull", owner=owner)
    library = OperatorResponseTypeDefinition(
        owner_user_id=owner.id,
        response_type="Soon-to-be-deleted",
        data_type="int",
        min=0.0,
        max=10.0,
    )
    db.add(library)
    db.flush()

    session_rtd = ResponseTypeDefinition(
        session_id=review_session.id,
        response_type="Soon-to-be-deleted",
        data_type="int",
        min=0.0,
        max=10.0,
        is_seeded=False,
        library_origin_id=library.id,
    )
    db.add(session_rtd)
    db.flush()
    session_rtd_id = session_rtd.id

    db.delete(library)
    db.flush()
    db.expire_all()

    fetched = db.execute(
        select(ResponseTypeDefinition).where(
            ResponseTypeDefinition.id == session_rtd_id
        )
    ).scalar_one()
    assert fetched.library_origin_id is None
    # Per-session content preserved.
    assert fetched.response_type == "Soon-to-be-deleted"
    assert fetched.data_type == "int"
