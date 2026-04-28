from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession, User
from app.schemas.validation import Severity
from app.services.validation import validate_session_setup


def _user(db: Session) -> User:
    user = User(email="op@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    return user


def _session(db: Session, user: User) -> ReviewSession:
    s = ReviewSession(name="Spring", code="spring-2026", created_by_user_id=user.id)
    db.add(s)
    db.flush()
    return s


def test_empty_session_reports_no_reviewers_and_no_reviewees(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)

    issues = validate_session_setup(db, session)

    errors = [i for i in issues if i.severity is Severity.error]
    sources = {i.source for i in errors}
    assert "reviewers" in sources
    assert "reviewees" in sources
    assert any(i.source == "instruments" and i.severity is Severity.info for i in issues)


def test_populated_session_has_no_errors(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    db.add(Reviewer(session_id=session.id, name="Alice", email="alice@example.edu"))
    db.add(
        Reviewee(
            session_id=session.id,
            name="Carol",
            email_or_identifier="carol@example.edu",
        )
    )
    db.flush()

    issues = validate_session_setup(db, session)

    assert [i for i in issues if i.severity is Severity.error] == []


def test_duplicate_reviewer_email_is_flagged(db: Session) -> None:
    user = _user(db)
    session = _session(db, user)
    db.add(Reviewer(session_id=session.id, name="Alice", email="dup@example.edu"))
    db.add(Reviewer(session_id=session.id, name="Alice2", email="DUP@example.edu"))
    db.add(
        Reviewee(
            session_id=session.id,
            name="Carol",
            email_or_identifier="carol@example.edu",
        )
    )
    db.flush()

    issues = validate_session_setup(db, session)

    dup = [i for i in issues if "Duplicate reviewer" in i.message]
    assert len(dup) == 1
    assert dup[0].severity is Severity.error
