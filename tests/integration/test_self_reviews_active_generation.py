"""Integration coverage for Segment 12C-1 PR 1 — generation paths
honour ``sessions.self_reviews_active``.

Post-15B Slice 3a, the wire-up flows through the page-level
Generate button on the Assignments page (POST
``/assignments/generate``) which calls
``replace_assignments(instrument_id=None)``. Tests pin the seeded
Full Matrix ``session_rule_sets`` row on every instrument, then
click Generate.

Pre-15B card-level ``exclude_self_review`` override retired with
the Rule Based card; the per-RuleSet ``exclude_self_reviews``
column on ``session_rule_sets`` is now the source of truth (the
seeded Full Matrix carries ``False`` so self-review pairs reach
the materialiser).
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Assignment, Reviewee, Reviewer, ReviewSession
from app.services import assignments as assignments_service
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


def _make_session(
    client: TestClient, db: Session, *, code: str, self_reviews_active: bool
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "SRA", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    if not self_reviews_active:
        review_session.self_reviews_active = False
        db.commit()
        db.refresh(review_session)
    return review_session


def _seed_population_with_self_review(
    client: TestClient, review_session: ReviewSession
) -> None:
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                (
                    b"ReviewerName,ReviewerEmail\n"
                    b"Alice,alice@example.edu\n"
                    b"Bob,bob@example.edu\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                (
                    b"RevieweeName,RevieweeEmail\n"
                    b"Alice,alice@example.edu\n"
                    b"Carol,carol@example.edu\n"
                ),
                "text/csv",
            )
        },
        follow_redirects=False,
    )


def _includes_by_pair(
    db: Session, session_id: int
) -> dict[tuple[str, str], bool]:
    rows = db.execute(
        select(Assignment, Reviewer, Reviewee)
        .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
        .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        .where(Assignment.session_id == session_id)
    ).all()
    return {
        (r.email, e.email_or_identifier): a.include for a, r, e in rows
    }


def test_full_matrix_self_review_inactive_when_flag_off(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(
        client, db, code="sra-fm-off", self_reviews_active=False
    )
    _seed_population_with_self_review(client, review_session)
    pin_full_matrix_on_all_instruments(db, review_session.id)

    response = generate_via_page_button(client, review_session.id)
    assert response.status_code == 303, response.text

    by_pair = _includes_by_pair(db, review_session.id)
    assert by_pair[("alice@example.edu", "alice@example.edu")] is False
    assert by_pair[("alice@example.edu", "carol@example.edu")] is True
    assert by_pair[("bob@example.edu", "alice@example.edu")] is True
    assert by_pair[("bob@example.edu", "carol@example.edu")] is True


def test_full_matrix_self_review_active_when_flag_on(
    client: TestClient, db: Session
) -> None:
    """Default ``self_reviews_active=True`` preserves pre-12C
    behaviour: self-review rows reach the table with ``include=True``."""

    review_session = _make_session(
        client, db, code="sra-fm-on", self_reviews_active=True
    )
    _seed_population_with_self_review(client, review_session)
    pin_full_matrix_on_all_instruments(db, review_session.id)

    response = generate_via_page_button(client, review_session.id)
    assert response.status_code == 303

    by_pair = _includes_by_pair(db, review_session.id)
    assert by_pair[("alice@example.edu", "alice@example.edu")] is True


def test_is_self_review_predicate_unchanged(db: Session) -> None:
    """Regression guard: the canonical predicate stayed identical to
    the 12A-1 PR 4a definition. (Case-insensitive email match;
    non-email reviewee identifier returns False.)"""

    alice_r = Reviewer(
        session_id=0, name="Alice", email="Alice@Example.edu"
    )
    alice_e = Reviewee(
        session_id=0, name="Alice", email_or_identifier="alice@example.edu"
    )
    dan_e = Reviewee(
        session_id=0, name="Dan", email_or_identifier="dan-2026"
    )
    assert assignments_service.is_self_review(alice_r, alice_e) is True
    assert assignments_service.is_self_review(alice_r, dan_e) is False
