"""18P PR C — the roster CSVs round-trip the active/inactive Status.

Reviewers / reviewees gain a ``Status`` column; the observer importer
reads the ``Status`` it already exported. A CSV without the column
imports everyone active (back-compat); an out-of-range value is a
blocking per-row error.
"""

from __future__ import annotations

import csv
import io

from sqlalchemy.orm import Session

from app.db.models import Observer, Reviewee, Reviewer, ReviewSession, User
from app.services.csv_imports import (
    parse_observer_csv,
    parse_reviewee_csv,
    parse_reviewer_csv,
)
from app.services.extracts.observers_extract import serialize_observers
from app.services.extracts.reviewees_extract import serialize_reviewees
from app.services.extracts.reviewers_extract import serialize_reviewers


def _session(db: Session, code: str) -> ReviewSession:
    user = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name=code.title(),
        code=code,
        created_by_user_id=user.id,
        observers_enabled=True,
    )
    db.add(review_session)
    db.flush()
    return review_session


def _csv_bytes(rows: list[tuple[str, ...]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")


def test_reviewer_status_round_trips(db: Session) -> None:
    review_session = _session(db, "rv-st")
    db.add_all(
        [
            Reviewer(
                session_id=review_session.id,
                name="Ana",
                email="ana@e.edu",
                status="active",
            ),
            Reviewer(
                session_id=review_session.id,
                name="Bo",
                email="bo@e.edu",
                status="inactive",
            ),
        ]
    )
    db.flush()
    result = parse_reviewer_csv(
        _csv_bytes(list(serialize_reviewers(db, review_session)))
    )
    assert result.issues == []
    by_email = {r.email: r.status for r in result.rows}
    assert by_email["ana@e.edu"] == "active"
    assert by_email["bo@e.edu"] == "inactive"


def test_reviewee_status_round_trips(db: Session) -> None:
    review_session = _session(db, "re-st")
    db.add_all(
        [
            Reviewee(
                session_id=review_session.id,
                name="Cy",
                email_or_identifier="cy@e.edu",
                status="active",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Di",
                email_or_identifier="di@e.edu",
                status="inactive",
            ),
        ]
    )
    db.flush()
    result = parse_reviewee_csv(
        _csv_bytes(list(serialize_reviewees(db, review_session)))
    )
    assert result.issues == []
    by_id = {r.email_or_identifier: r.status for r in result.rows}
    assert by_id["cy@e.edu"] == "active"
    assert by_id["di@e.edu"] == "inactive"


def test_observer_status_round_trips(db: Session) -> None:
    review_session = _session(db, "ob-st")
    db.add_all(
        [
            Observer(
                session_id=review_session.id,
                email="ea@e.edu",
                status="active",
            ),
            Observer(
                session_id=review_session.id,
                email="fi@e.edu",
                status="inactive",
            ),
        ]
    )
    db.flush()
    result = parse_observer_csv(
        _csv_bytes(list(serialize_observers(db, review_session)))
    )
    assert result.issues == []
    by_email = {r.email: r.status for r in result.rows}
    assert by_email["ea@e.edu"] == "active"
    assert by_email["fi@e.edu"] == "inactive"


def test_missing_status_column_defaults_active(db: Session) -> None:
    rows = [("ReviewerName", "ReviewerEmail"), ("Ana", "ana@e.edu")]
    result = parse_reviewer_csv(_csv_bytes(rows))
    assert result.issues == []
    assert result.rows[0].status == "active"


def test_invalid_status_rejected(db: Session) -> None:
    rows = [
        ("ReviewerName", "ReviewerEmail", "Status"),
        ("Ana", "ana@e.edu", "archived"),
    ]
    result = parse_reviewer_csv(_csv_bytes(rows))
    assert result.rows == []
    assert any(issue.field == "Status" for issue in result.issues)
