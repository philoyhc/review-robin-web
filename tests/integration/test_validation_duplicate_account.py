"""Validate warns on two active rows in one roster bound to one directory
account (segment 19Z, upsert amendment): one person entered twice, by
mail and by sign-in name, which the duplicate-address rules cannot see.
Non-blocking; inactive rows are not counted.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, Reviewer, ReviewSession, User
from app.schemas.validation import Severity
from app.services.validation import validate_session_setup

JANE = "11111111-1111-4111-8111-111111111111"


def _session(db: Session) -> ReviewSession:
    owner = User(email="op-dupacct@example.edu")
    db.add(owner)
    db.flush()
    review_session = ReviewSession(name="Dup", code="dup-acct", created_by_user_id=owner.id)
    db.add(review_session)
    db.flush()
    return review_session


def _issues(db: Session, review_session: ReviewSession, key: str):
    return [i for i in validate_session_setup(db, review_session) if i.rule_key == key]


def test_two_rows_on_one_account_warn_on_each_roster(db: Session) -> None:
    s = _session(db)
    db.add_all(
        [
            Reviewer(session_id=s.id, name="Jane", email="jane.tan@example.edu", directory_object_id=JANE),
            Reviewer(session_id=s.id, name="Jane", email="e0123456@example.edu", directory_object_id=JANE.upper()),
            Reviewer(session_id=s.id, name="Lee", email="lee@example.edu"),
            Reviewee(session_id=s.id, name="Jane", email_or_identifier="jane.tan@example.edu", directory_object_id=JANE),
            Reviewee(session_id=s.id, name="Jane", email_or_identifier="e0123456@example.edu", directory_object_id=JANE),
            Observer(session_id=s.id, email="jane.tan@example.edu", directory_object_id=JANE),
            Observer(session_id=s.id, email="e0123456@example.edu", directory_object_id=JANE),
        ]
    )
    db.flush()

    for key in ("reviewers.duplicate_account", "reviewees.duplicate_account", "observers.duplicate_account"):
        issues = _issues(db, s, key)
        assert len(issues) == 1, key
        assert issues[0].severity is Severity.warning
        assert "'jane.tan@example.edu'" in issues[0].message and "'e0123456@example.edu'" in issues[0].message
    # The duplicate-address rules see two different addresses.
    assert _issues(db, s, "reviewers.duplicate_email") == []


def test_an_inactive_or_unbound_row_is_not_counted(db: Session) -> None:
    s = _session(db)
    db.add_all(
        [
            Reviewer(session_id=s.id, name="Jane", email="jane.tan@example.edu", directory_object_id=JANE),
            Reviewer(session_id=s.id, name="Jane", email="e0123456@example.edu", directory_object_id=JANE, status="inactive"),
            Reviewer(session_id=s.id, name="Pat", email="pat@example.edu"),
            Reviewer(session_id=s.id, name="Pat", email="pat.lim@example.edu"),
        ]
    )
    db.flush()
    assert _issues(db, s, "reviewers.duplicate_account") == []
