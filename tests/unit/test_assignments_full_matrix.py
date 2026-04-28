from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession, User
from app.services.assignments import (
    generate_full_matrix,
    get_or_create_default_instrument,
)


def _user(db: Session) -> User:
    user = User(email="op@example.edu")
    db.add(user)
    db.flush()
    return user


def _session(db: Session, user: User) -> ReviewSession:
    s = ReviewSession(name="Spring", code="spring", created_by_user_id=user.id)
    db.add(s)
    db.flush()
    return s


def _reviewer(db: Session, session_id: int, name: str, email: str) -> Reviewer:
    r = Reviewer(session_id=session_id, name=name, email=email)
    db.add(r)
    db.flush()
    return r


def _reviewee(db: Session, session_id: int, name: str, ident: str) -> Reviewee:
    r = Reviewee(session_id=session_id, name=name, email_or_identifier=ident)
    db.add(r)
    db.flush()
    return r


def test_full_matrix_pairs_every_reviewer_with_every_reviewee(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    reviewers = [
        _reviewer(db, session.id, "Alice", "alice@example.edu"),
        _reviewer(db, session.id, "Bob", "bob@example.edu"),
    ]
    reviewees = [
        _reviewee(db, session.id, "Carol", "carol@example.edu"),
        _reviewee(db, session.id, "Dan", "dan-2026"),
        _reviewee(db, session.id, "Eve", "eve@example.edu"),
    ]

    pairs, excluded = generate_full_matrix(
        reviewers, reviewees, exclude_self_review=False
    )

    assert len(pairs) == 6
    assert excluded == {}


def test_full_matrix_excludes_self_review_when_emails_match(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    alice_r = _reviewer(db, session.id, "Alice", "alice@example.edu")
    bob_r = _reviewer(db, session.id, "Bob", "bob@example.edu")
    alice_e = _reviewee(db, session.id, "Alice", "ALICE@example.edu")
    carol_e = _reviewee(db, session.id, "Carol", "carol@example.edu")

    pairs, excluded = generate_full_matrix(
        [alice_r, bob_r], [alice_e, carol_e], exclude_self_review=True
    )

    assert excluded == {"self_review": 1}
    assert (alice_r, alice_e) not in pairs
    assert (alice_r, carol_e) in pairs
    assert (bob_r, alice_e) in pairs
    assert (bob_r, carol_e) in pairs


def test_full_matrix_does_not_exclude_when_reviewee_has_no_at_sign(
    db: Session,
) -> None:
    user = _user(db)
    session = _session(db, user)
    alice_r = _reviewer(db, session.id, "Alice", "alice@example.edu")
    dan_e = _reviewee(db, session.id, "Dan", "alice")

    pairs, excluded = generate_full_matrix(
        [alice_r], [dan_e], exclude_self_review=True
    )

    assert excluded == {}
    assert pairs == [(alice_r, dan_e)]


def test_full_matrix_skips_inactive_reviewers(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    alice = _reviewer(db, session.id, "Alice", "alice@example.edu")
    bob = _reviewer(db, session.id, "Bob", "bob@example.edu")
    bob.status = "inactive"
    carol = _reviewee(db, session.id, "Carol", "carol@example.edu")
    db.flush()

    pairs, excluded = generate_full_matrix(
        [alice, bob], [carol], exclude_self_review=False
    )

    assert pairs == [(alice, carol)]
    assert excluded == {"inactive_reviewer": 1}


def test_full_matrix_skips_inactive_reviewees(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    alice = _reviewer(db, session.id, "Alice", "alice@example.edu")
    carol = _reviewee(db, session.id, "Carol", "carol@example.edu")
    dan = _reviewee(db, session.id, "Dan", "dan-2026")
    dan.status = "inactive"
    db.flush()

    pairs, excluded = generate_full_matrix(
        [alice], [carol, dan], exclude_self_review=False
    )

    assert pairs == [(alice, carol)]
    assert excluded == {"inactive_reviewee": 1}


def test_get_or_create_default_instrument_is_idempotent(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)

    first = get_or_create_default_instrument(db, session)
    second = get_or_create_default_instrument(db, session)

    assert first.id == second.id
    assert first.name == "Default"
    assert first.session_id == session.id
