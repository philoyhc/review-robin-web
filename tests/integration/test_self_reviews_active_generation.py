"""Integration coverage for Segment 12C-1 PR 1 — generation paths
honour ``sessions.self_reviews_active``.

Exercises the wire-up via
``POST /assignments/rule-based/generate`` against the seeded
Full Matrix RuleSet, with the card-level
``exclude_self_review=false`` override so self-review pairs do
reach ``replace_assignments``.

We seed a session whose population includes an email-matching
reviewer / reviewee pair, flip the session-level
``self_reviews_active`` flag to ``False``, run the generation,
and assert that the self-review row landed with ``include=False``
while the non-self-review rows landed with ``include=True``.

When the flag is ``True`` (the default), self-review rows still
land with ``include=True`` — the pre-12C behaviour.
"""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Assignment, Reviewee, Reviewer, ReviewSession, RuleSet
from app.services import assignments as assignments_service
from ._full_matrix import full_matrix_seed_id


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
    """Alice appears as both a reviewer and a reviewee — that pair is
    the self-review the test pivots on."""

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


def test_full_matrix_seed_route_self_review_inactive_when_flag_off(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(
        client, db, code="sra-fm-off", self_reviews_active=False
    )
    _seed_population_with_self_review(client, review_session)

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={
            "rule_set_id": full_matrix_seed_id(db),
            "exclude_self_review": "false",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    by_pair = _includes_by_pair(db, review_session.id)
    assert by_pair[("alice@example.edu", "alice@example.edu")] is False
    # Non-self-review rows stay active.
    assert by_pair[("alice@example.edu", "carol@example.edu")] is True
    assert by_pair[("bob@example.edu", "alice@example.edu")] is True
    assert by_pair[("bob@example.edu", "carol@example.edu")] is True


def test_full_matrix_seed_route_self_review_active_when_flag_on(
    client: TestClient, db: Session
) -> None:
    """Default ``self_reviews_active=True`` preserves pre-12C behaviour:
    self-review rows reach the table with ``include=True``."""

    review_session = _make_session(
        client, db, code="sra-fm-on", self_reviews_active=True
    )
    _seed_population_with_self_review(client, review_session)

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={
            "rule_set_id": full_matrix_seed_id(db),
            "exclude_self_review": "false",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303

    by_pair = _includes_by_pair(db, review_session.id)
    assert by_pair[("alice@example.edu", "alice@example.edu")] is True


def test_rule_based_generate_self_review_inactive_when_flag_off(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(
        client, db, code="sra-rb-off", self_reviews_active=False
    )
    _seed_population_with_self_review(client, review_session)

    full_matrix_id = db.execute(
        select(RuleSet.id).where(
            RuleSet.is_seed.is_(True), RuleSet.name == "Full Matrix"
        )
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/assignments/rule-based/generate",
        data={
            "rule_set_id": full_matrix_id,
            # Card-level override to KEEP self-reviews so they reach
            # replace_assignments — that's the wire-up under test.
            "exclude_self_review": "false",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    by_pair = _includes_by_pair(db, review_session.id)
    assert by_pair[("alice@example.edu", "alice@example.edu")] is False
    assert by_pair[("alice@example.edu", "carol@example.edu")] is True
    assert by_pair[("bob@example.edu", "alice@example.edu")] is True


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
