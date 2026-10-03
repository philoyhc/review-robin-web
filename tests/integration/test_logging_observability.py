"""Segment 14A PR 1 — structured-logging emission at the §5.3 points.

Verifies the application-log stream fires (and carries its
structured ``extra`` fields) at session activation, roster
import / delete, retention purge, and permission denial. The
JSON-formatter shape itself is covered in
``tests/unit/test_logging_config.py``.
"""
from __future__ import annotations

import logging

import pytest
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, SessionOperator, User
from app.schemas.imports import ReviewerImportRow
from app.services import csv_imports, session_purge
from app.services.csv_imports import decode_csv
from app.web.deps import OperatorAllowlistDenied, require_operator


def _seed(db: Session) -> tuple[User, ReviewSession]:
    op = User(email="op@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    review_session = ReviewSession(
        name="Spring", code="spring-2026", created_by_user_id=op.id
    )
    db.add(review_session)
    db.flush()
    db.add(SessionOperator(session_id=review_session.id, user_id=op.id, role="owner"))
    db.flush()
    return op, review_session


def _records(caplog: pytest.LogCaptureFixture, message: str) -> list[logging.LogRecord]:
    return [r for r in caplog.records if r.getMessage() == message]


def test_oversized_csv_logs_rejection(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        decode_csv(b"x" * 10, "reviewers", max_bytes=4)

    rejected = _records(caplog, "csv import rejected")
    assert len(rejected) == 1
    assert rejected[0].reason == "too_large"
    assert rejected[0].source == "reviewers"


def test_non_utf8_csv_logs_rejection(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        decode_csv(b"\xff\xfe\x00bad", "reviewees")

    rejected = _records(caplog, "csv import rejected")
    assert len(rejected) == 1
    assert rejected[0].reason == "not_utf8"


def test_roster_import_logs_outcome(
    db: Session, caplog: pytest.LogCaptureFixture
) -> None:
    op, review_session = _seed(db)

    with caplog.at_level(logging.INFO):
        csv_imports.save_reviewers(
            db,
            session=review_session,
            user=op,
            rows=[ReviewerImportRow(name="Rae", email="rae@example.edu")],
            filename="reviewers.csv",
            correlation_id="corr-1",
        )

    imported = _records(caplog, "roster imported")
    assert len(imported) == 1
    assert imported[0].session_id == review_session.id
    assert imported[0].source == "reviewers"
    assert imported[0].new == 1
    assert imported[0].correlation_id == "corr-1"


def test_purge_responses_logs_retention_action(
    db: Session, caplog: pytest.LogCaptureFixture
) -> None:
    op, review_session = _seed(db)

    with caplog.at_level(logging.INFO):
        session_purge.purge_responses(
            db, review_session=review_session, user=op, correlation_id="corr-2"
        )

    purged = _records(caplog, "session data purged")
    assert len(purged) == 1
    assert purged[0].kind == "responses"
    assert purged[0].session_id == review_session.id


def test_permission_denial_logs_warning(
    db: Session, caplog: pytest.LogCaptureFixture
) -> None:
    bob = User(
        email="bob@example.edu",
        display_name="Bob",
        is_operator=False,
        is_sys_admin=False,
    )
    db.add(bob)
    db.flush()

    with caplog.at_level(logging.WARNING):
        with pytest.raises(OperatorAllowlistDenied):
            require_operator(user=bob)

    denied = _records(caplog, "permission denied")
    assert len(denied) == 1
    assert denied[0].gate == "require_operator"
    assert denied[0].user_id == bob.id


def test_grant_denial_logs_the_user_and_the_reviewee(
    db: Session, caplog: pytest.LogCaptureFixture
) -> None:
    """``require_reviewee_with_current_grant`` logged the reviewee's id
    under ``user_id``; it now logs the signed-in user's id there and the
    reviewee's under ``reviewee_id`` (findings 2026-10-03 A4)."""
    from fastapi import HTTPException

    from app.db.models import Reviewee
    from app.web.deps import require_reviewee_with_current_grant

    owner = User(email="owner-a4@example.edu", display_name="Owner")
    ree = User(email="ree-a4@example.edu", display_name="Ree")
    db.add_all([owner, ree])
    db.flush()
    review_session = ReviewSession(
        name="A4", code="a4-log", created_by_user_id=owner.id
    )
    db.add(review_session)
    db.flush()
    # Pad the reviewee table so the two ids cannot coincide.
    db.add_all(
        Reviewee(
            session_id=review_session.id,
            name=f"Pad {n}",
            email_or_identifier=f"pad{n}@example.edu",
        )
        for n in range(ree.id + 1)
    )
    reviewee = Reviewee(
        session_id=review_session.id,
        name="Ree",
        email_or_identifier=ree.email,
    )
    db.add(reviewee)
    db.flush()
    assert reviewee.id != ree.id

    with caplog.at_level(logging.WARNING):
        with pytest.raises(HTTPException):
            require_reviewee_with_current_grant(
                reviewee_session=(reviewee, review_session), user=ree, db=db
            )

    denied = _records(caplog, "permission denied")
    assert len(denied) == 1
    assert denied[0].gate == "require_reviewee_with_current_grant"
    assert denied[0].user_id == ree.id
    assert denied[0].reviewee_id == reviewee.id
