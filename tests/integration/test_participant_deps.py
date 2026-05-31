"""Integration tests for ``require_reviewee_in_session`` and
``require_observer_in_session`` — the Phase 1 dep stubs in
``app/web/deps.py``.

Exercised by direct dependency invocation (no route mounts them
yet). The auth surfaces will mount them in Phase 3 (W16 / W17).
See ``guide/participant_model_upgrade.md`` §4 and
``guide/participant_model_prep.md`` rows W2, W3.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException, Request, status
from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, ReviewSession, User
from app.web.deps import (
    require_observer_in_session,
    require_reviewee_in_session,
)


def _request() -> Request:
    return Request({"type": "http"})


def _session(db: Session, *, code: str = "pdep") -> ReviewSession:
    user = User(email=f"{code}-op@x.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="P",
        code=code,
        created_by_user_id=user.id,
        assignment_mode="manual",
    )
    db.add(review_session)
    db.flush()
    return review_session


def _user(db: Session, email: str) -> User:
    u = User(email=email, display_name=email)
    db.add(u)
    db.flush()
    return u


# ---------------------------------------------------------------- reviewee


def test_reviewee_dep_404_when_session_missing(db: Session) -> None:
    me = _user(db, "me@example.org")
    with pytest.raises(HTTPException) as exc:
        require_reviewee_in_session(
            session_id=999_999, request=_request(), user=me, db=db
        )
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


def test_reviewee_dep_403_when_no_matching_row(db: Session) -> None:
    s = _session(db, code="rvd-1")
    me = _user(db, "me@example.org")
    with pytest.raises(HTTPException) as exc:
        require_reviewee_in_session(
            session_id=s.id, request=_request(), user=me, db=db
        )
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN


def test_reviewee_dep_returns_match_on_email(db: Session) -> None:
    s = _session(db, code="rvd-2")
    me = _user(db, "me@example.org")
    db.add(
        Reviewee(
            session_id=s.id,
            name="Me",
            email_or_identifier="me@example.org",
        )
    )
    db.commit()
    matched, review_session = require_reviewee_in_session(
        session_id=s.id, request=_request(), user=me, db=db
    )
    assert matched.email_or_identifier == "me@example.org"
    assert review_session.id == s.id


def test_reviewee_dep_case_insensitive_email_match(db: Session) -> None:
    s = _session(db, code="rvd-3")
    me = _user(db, "ME@Example.ORG")
    db.add(
        Reviewee(
            session_id=s.id,
            name="Me",
            email_or_identifier="me@example.org",
        )
    )
    db.commit()
    matched, _ = require_reviewee_in_session(
        session_id=s.id, request=_request(), user=me, db=db
    )
    assert matched is not None


def test_reviewee_dep_rejects_non_email_identifier(db: Session) -> None:
    # A reviewee with a non-email identifier — the confidential /
    # unaware-subject case. Even if a user's email string happens
    # to coincide with the identifier value, the surface stays
    # gated off by is_email_identified.
    s = _session(db, code="rvd-4")
    me = _user(db, "anon-007")  # not a real email
    db.add(
        Reviewee(
            session_id=s.id, name="Anon", email_or_identifier="anon-007"
        )
    )
    db.commit()
    with pytest.raises(HTTPException) as exc:
        require_reviewee_in_session(
            session_id=s.id, request=_request(), user=me, db=db
        )
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN


def test_reviewee_dep_inactive_status_denied(db: Session) -> None:
    s = _session(db, code="rvd-5")
    me = _user(db, "me@example.org")
    db.add(
        Reviewee(
            session_id=s.id,
            name="Me",
            email_or_identifier="me@example.org",
            status="inactive",
        )
    )
    db.commit()
    with pytest.raises(HTTPException) as exc:
        require_reviewee_in_session(
            session_id=s.id, request=_request(), user=me, db=db
        )
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------- observer


def test_observer_dep_404_when_session_missing(db: Session) -> None:
    me = _user(db, "me@example.org")
    with pytest.raises(HTTPException) as exc:
        require_observer_in_session(
            session_id=999_999, request=_request(), user=me, db=db
        )
    assert exc.value.status_code == status.HTTP_404_NOT_FOUND


def test_observer_dep_403_when_no_matching_row(db: Session) -> None:
    s = _session(db, code="obd-1")
    me = _user(db, "me@example.org")
    with pytest.raises(HTTPException) as exc:
        require_observer_in_session(
            session_id=s.id, request=_request(), user=me, db=db
        )
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN


def test_observer_dep_returns_match_on_email(db: Session) -> None:
    s = _session(db, code="obd-2")
    me = _user(db, "me@example.org")
    db.add(Observer(session_id=s.id, email="me@example.org"))
    db.commit()
    matched, review_session = require_observer_in_session(
        session_id=s.id, request=_request(), user=me, db=db
    )
    assert matched.email == "me@example.org"
    assert review_session.id == s.id


def test_observer_dep_case_insensitive_email_match(db: Session) -> None:
    s = _session(db, code="obd-3")
    me = _user(db, "ME@Example.ORG")
    db.add(Observer(session_id=s.id, email="me@example.org"))
    db.commit()
    matched, _ = require_observer_in_session(
        session_id=s.id, request=_request(), user=me, db=db
    )
    assert matched is not None


def test_observer_dep_inactive_status_denied(db: Session) -> None:
    s = _session(db, code="obd-4")
    me = _user(db, "me@example.org")
    db.add(
        Observer(
            session_id=s.id, email="me@example.org", status="inactive"
        )
    )
    db.commit()
    with pytest.raises(HTTPException) as exc:
        require_observer_in_session(
            session_id=s.id, request=_request(), user=me, db=db
        )
    assert exc.value.status_code == status.HTTP_403_FORBIDDEN
