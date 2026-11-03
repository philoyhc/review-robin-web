"""Validate's ``reviewees.mirror_drift`` (segment 20F rung 2): under
symmetric review the Reviewees roster is a copy of the Reviewers roster,
kept by ``symmetric_review.sync_reviewees_from_reviewers`` on every
reviewer write. The rule reports what a writer that skipped the sync would
leave: a reviewer with no mirror, a reviewee mirroring no reviewer, and a
mirrored field that differs. Each case is made here by writing the
database directly, as such a writer would.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession, User
from app.services import csv_imports
from app.services.validation import validate_session_setup

RULE = "reviewees.mirror_drift"


def _session(client: TestClient, db: Session, code: str, *, on: bool = True) -> ReviewSession:
    data = {"name": "Sym", "code": code, "description": ""}
    if on:
        data["symmetric_review"] = "true"
    response = client.post("/operator/sessions", data=data, follow_redirects=False)
    assert response.status_code == 303
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    parsed = csv_imports.parse_reviewer_csv(
        b"ReviewerName,ReviewerEmail\nAnn,ann@example.edu\nBob,bob@example.edu\n"
    )
    owner = db.execute(select(User).order_by(User.id)).scalars().first()
    csv_imports.save_reviewers(
        db, session=review_session, user=owner, rows=parsed.rows,
        filename="r.csv", correlation_id="c",
    )
    db.commit()
    return review_session


def _drift(db: Session, review_session: ReviewSession) -> list[str]:
    db.expire_all()
    return [
        issue.message
        for issue in validate_session_setup(db, review_session)
        if issue.rule_key == RULE
    ]


def _reviewee(db: Session, review_session: ReviewSession, email: str) -> Reviewee:
    return db.execute(
        select(Reviewee).where(
            Reviewee.session_id == review_session.id, Reviewee.email_or_identifier == email
        )
    ).scalar_one()


def test_a_synced_roster_reports_nothing(client: TestClient, db: Session) -> None:
    assert _drift(db, _session(client, db, "md-clean")) == []


def test_a_mirrored_field_that_differs_is_reported(client: TestClient, db: Session) -> None:
    review_session = _session(client, db, "md-field")
    _reviewee(db, review_session, "ann@example.edu").name = "Anne"
    db.commit()
    assert _drift(db, review_session) == [
        "Reviewee 'ann@example.edu' differs from its reviewer in name"
    ]


def test_a_reviewer_without_a_mirror_is_reported(client: TestClient, db: Session) -> None:
    review_session = _session(client, db, "md-missing")
    db.add(Reviewer(session_id=review_session.id, name="Cy", email="cy@example.edu"))
    db.commit()
    assert _drift(db, review_session) == ["Reviewer 'cy@example.edu' has no mirrored reviewee"]


def test_a_reviewee_mirroring_no_reviewer_is_reported(client: TestClient, db: Session) -> None:
    review_session = _session(client, db, "md-orphan")
    db.add(Reviewee(session_id=review_session.id, name="Di", email_or_identifier="di@example.edu"))
    db.commit()
    assert _drift(db, review_session) == [
        "Reviewee 'di@example.edu' mirrors no reviewer on the roster"
    ]


def test_a_reviewer_save_brings_the_copy_back_into_step(client: TestClient, db: Session) -> None:
    """The rule's fix line: any reviewer save re-runs the sync."""
    from app.services import symmetric_review

    review_session = _session(client, db, "md-fix")
    _reviewee(db, review_session, "ann@example.edu").name = "Anne"
    db.commit()
    symmetric_review.sync_reviewees_from_reviewers(db, review_session)
    db.commit()
    assert _drift(db, review_session) == []


def test_nothing_is_checked_with_the_mode_off(client: TestClient, db: Session) -> None:
    review_session = _session(client, db, "md-off", on=False)
    db.add(Reviewee(session_id=review_session.id, name="Di", email_or_identifier="di@example.edu"))
    db.commit()
    assert _drift(db, review_session) == []
