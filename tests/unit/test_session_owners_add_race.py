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
    # The other request's row landed after this one's check.
    monkeypatch.setattr(session_owners, "_is_owner", lambda *_: False)

    with pytest.raises(session_owners.OwnerOperationError) as exc:
        session_owners.add_owner(
            db, review_session=review_session, actor=alice, target=bob
        )

    assert exc.value.code == "already_owner"
    assert len(session_owners.list_owners(db, review_session)) == 2
    assert not db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "session.owner_added")
    ).first()
