"""``session_owners.add_owner`` under a race (19S Item 10).

Session Home's Add owner saves at once, so two operators adding the same
address can both pass the ``already_owner`` check. ``uq_session_user``
refuses the second insert; the service turns that into the same
``already_owner`` refusal the card's banner renders, not a 500, and the
refusal leaves the caller's transaction usable.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession, SessionOperator, User
from app.services import session_owners


def test_a_duplicate_insert_is_refused_already_owner(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    alice = User(email="alice@example.edu", is_operator=True)
    bob = User(email="bob@example.edu", is_operator=True)
    db.add_all([alice, bob])
    db.flush()
    review_session = ReviewSession(
        name="Race", code="RACE-1", created_by_user_id=alice.id
    )
    db.add(review_session)
    db.flush()
    db.add_all(
        [
            SessionOperator(session_id=review_session.id, user_id=alice.id, role="owner"),
            SessionOperator(session_id=review_session.id, user_id=bob.id, role="owner"),
        ]
    )
    db.flush()
    # The other request's row landed after this one's check: the first
    # look misses it, the look after the refused insert sees it.
    real = session_owners._is_owner
    looks: list[bool] = []

    def late_is_owner(*args: object) -> bool:
        looks.append(True)
        return False if len(looks) == 1 else real(*args)

    monkeypatch.setattr(session_owners, "_is_owner", late_is_owner)

    with pytest.raises(session_owners.OwnerOperationError) as exc:
        session_owners.add_owner(
            db, review_session=review_session, actor=alice, target=bob
        )

    assert exc.value.code == "already_owner"
    assert len(looks) == 2
    assert len(session_owners.list_owners(db, review_session)) == 2
    assert not db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "session.owner_added")
    ).first()


def test_an_integrity_error_that_is_not_the_duplicate_still_raises(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the ``uq_session_user`` race becomes ``already_owner``."""
    alice = User(email="alice@example.edu", is_operator=True)
    bob = User(email="bob@example.edu", is_operator=True)
    db.add_all([alice, bob])
    db.flush()
    review_session = ReviewSession(
        name="Race", code="RACE-2", created_by_user_id=alice.id
    )
    db.add(review_session)
    db.flush()

    def failing_insert(*_: object, **__: object) -> None:
        raise IntegrityError("INSERT", {}, Exception("fk"))

    monkeypatch.setattr(session_owners, "_insert_owner", failing_insert)

    with pytest.raises(IntegrityError):
        session_owners.add_owner(
            db, review_session=review_session, actor=alice, target=bob
        )
