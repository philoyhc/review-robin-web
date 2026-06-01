"""Unit tests for the ``Observer`` model — pins the per-session
roster contract (UNIQUE on session_id + email; ``session.observers``
cascade) before Phase 2 / Phase 3 slices build on top.

See ``guide/archive/participant_model_upgrade.md`` §3.1 and
``guide/archive/participant_model_upgrade.md`` row S1.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Observer, ReviewSession, User


def _session(db: Session, *, code: str = "obs") -> ReviewSession:
    user = User(email=f"{code}@x.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Obs", code=code, created_by_user_id=user.id, assignment_mode="manual"
    )
    db.add(review_session)
    db.flush()
    return review_session


def test_observer_persists_and_refetches(db: Session) -> None:
    review_session = _session(db)
    observer = Observer(
        session_id=review_session.id,
        email="chair@example.org",
        display_name="Committee Chair",
        tag_1="committee",
    )
    db.add(observer)
    db.commit()

    refetched = db.get(Observer, observer.id)
    assert refetched is not None
    assert refetched.email == "chair@example.org"
    assert refetched.display_name == "Committee Chair"
    assert refetched.status == "active"
    assert refetched.tag_1 == "committee"


def test_observer_display_name_and_tag_optional(db: Session) -> None:
    review_session = _session(db)
    observer = Observer(
        session_id=review_session.id, email="nobody@example.org"
    )
    db.add(observer)
    db.commit()

    refetched = db.get(Observer, observer.id)
    assert refetched is not None
    assert refetched.display_name is None
    assert refetched.tag_1 is None


def test_observer_unique_per_session_email(db: Session) -> None:
    review_session = _session(db)
    db.add(
        Observer(session_id=review_session.id, email="dup@example.org")
    )
    db.commit()

    db.add(
        Observer(session_id=review_session.id, email="dup@example.org")
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_observer_same_email_across_sessions_allowed(db: Session) -> None:
    s1 = _session(db, code="obs-a")
    s2 = _session(db, code="obs-b")
    db.add(Observer(session_id=s1.id, email="shared@example.org"))
    db.add(Observer(session_id=s2.id, email="shared@example.org"))
    db.commit()  # would raise if the UNIQUE wasn't (session_id, email)


def test_session_observers_cascade(db: Session) -> None:
    review_session = _session(db)
    db.add(Observer(session_id=review_session.id, email="x@example.org"))
    db.add(Observer(session_id=review_session.id, email="y@example.org"))
    db.commit()
    session_id = review_session.id

    db.delete(review_session)
    db.commit()

    remaining = (
        db.query(Observer).filter(Observer.session_id == session_id).count()
    )
    assert remaining == 0
