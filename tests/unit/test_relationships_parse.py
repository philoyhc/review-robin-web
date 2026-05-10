"""Unit coverage for ``parse_relationship_csv`` (Segment 15D PR 1).

Mirrors the existing unit-test conventions for
``parse_reviewer_csv`` / ``parse_reviewee_csv``: parse a CSV byte
buffer against fixture roster lists; assert the parsed rows and
the validation issues. No DB save here — that's the integration
test's job.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession, User
from app.services.relationships import parse_relationship_csv


def _seed(db: Session) -> tuple[Reviewer, Reviewer, Reviewee, Reviewee]:
    user = User(email="op@example.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Spring", code="rel-parse", created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    alice = Reviewer(
        session_id=review_session.id, name="Alice", email="alice@example.edu"
    )
    bob = Reviewer(
        session_id=review_session.id, name="Bob", email="bob@example.edu"
    )
    carol = Reviewee(
        session_id=review_session.id,
        name="Carol",
        email_or_identifier="carol@example.edu",
    )
    dan = Reviewee(
        session_id=review_session.id,
        name="Dan",
        email_or_identifier="dan-2026",
    )
    db.add_all([alice, bob, carol, dan])
    db.flush()
    return alice, bob, carol, dan


def test_parse_happy_path(db: Session) -> None:
    """Two valid rows produce two ``RelationshipImportRow`` rows
    with the resolved FKs + tag values + default status."""

    alice, bob, carol, dan = _seed(db)

    csv_body = (
        b"ReviewerEmail,RevieweeEmail,PairContextTag1,PairContextTag2,"
        b"PairContextTag3,Status\n"
        b"alice@example.edu,carol@example.edu,Mentor,,,active\n"
        b"bob@example.edu,dan-2026,,,Prior cohort,\n"
    )
    result = parse_relationship_csv(
        csv_body, reviewers=[alice, bob], reviewees=[carol, dan]
    )

    assert result.issues == []
    assert len(result.rows) == 2

    first, second = result.rows
    assert first.reviewer_id == alice.id
    assert first.reviewee_id == carol.id
    assert first.tag_1 == "Mentor"
    assert first.tag_2 is None
    assert first.tag_3 is None
    assert first.status == "active"

    assert second.reviewer_id == bob.id
    assert second.reviewee_id == dan.id
    assert second.tag_1 is None
    assert second.tag_3 == "Prior cohort"
    # Empty status cell defaults to "active".
    assert second.status == "active"


def test_parse_inactive_status_round_trips(db: Session) -> None:
    alice, _bob, carol, _dan = _seed(db)
    csv_body = (
        b"ReviewerEmail,RevieweeEmail,Status\n"
        b"alice@example.edu,carol@example.edu,inactive\n"
    )
    result = parse_relationship_csv(
        csv_body, reviewers=[alice], reviewees=[carol]
    )
    assert result.issues == []
    assert len(result.rows) == 1
    assert result.rows[0].status == "inactive"


def test_parse_unknown_reviewer_email(db: Session) -> None:
    """Email that doesn't match any session reviewer surfaces a
    row-level validation error."""

    _alice, _bob, carol, _dan = _seed(db)
    csv_body = (
        b"ReviewerEmail,RevieweeEmail\n"
        b"ghost@example.edu,carol@example.edu\n"
    )
    result = parse_relationship_csv(
        csv_body, reviewers=[], reviewees=[carol]
    )
    assert result.rows == []
    assert len(result.issues) == 1
    issue = result.issues[0]
    assert issue.field == "ReviewerEmail"
    assert issue.row_number == 1
    assert "ghost@example.edu" in issue.message


def test_parse_unknown_reviewee_identifier(db: Session) -> None:
    alice, _bob, _carol, _dan = _seed(db)
    csv_body = (
        b"ReviewerEmail,RevieweeEmail\n"
        b"alice@example.edu,nobody@example.edu\n"
    )
    result = parse_relationship_csv(
        csv_body, reviewers=[alice], reviewees=[]
    )
    assert result.rows == []
    assert len(result.issues) == 1
    assert result.issues[0].field == "RevieweeEmail"


def test_parse_duplicate_pair(db: Session) -> None:
    """Two rows referencing the same (reviewer, reviewee) pair
    surface a row-level error on the second occurrence."""

    alice, _bob, carol, _dan = _seed(db)
    csv_body = (
        b"ReviewerEmail,RevieweeEmail,PairContextTag1\n"
        b"alice@example.edu,carol@example.edu,Mentor\n"
        b"alice@example.edu,carol@example.edu,COI\n"
    )
    result = parse_relationship_csv(
        csv_body, reviewers=[alice], reviewees=[carol]
    )
    # The first row parses; the second row is rejected.
    assert len(result.rows) == 1
    assert len(result.issues) == 1
    assert "Duplicate pair" in result.issues[0].message
    assert result.issues[0].row_number == 2


def test_parse_invalid_status(db: Session) -> None:
    alice, _bob, carol, _dan = _seed(db)
    csv_body = (
        b"ReviewerEmail,RevieweeEmail,Status\n"
        b"alice@example.edu,carol@example.edu,suspended\n"
    )
    result = parse_relationship_csv(
        csv_body, reviewers=[alice], reviewees=[carol]
    )
    assert result.rows == []
    assert len(result.issues) == 1
    assert result.issues[0].field == "Status"


def test_parse_missing_required_column(db: Session) -> None:
    alice, _bob, carol, _dan = _seed(db)
    csv_body = (
        b"ReviewerEmail\n"
        b"alice@example.edu\n"
    )
    result = parse_relationship_csv(
        csv_body, reviewers=[alice], reviewees=[carol]
    )
    assert result.rows == []
    assert any(
        issue.field == "RevieweeEmail" or "RevieweeEmail" in issue.message
        for issue in result.issues
    )


def test_parse_resolves_email_case_insensitively(db: Session) -> None:
    alice, _bob, carol, _dan = _seed(db)
    csv_body = (
        b"ReviewerEmail,RevieweeEmail\n"
        b"ALICE@example.edu,Carol@Example.edu\n"
    )
    result = parse_relationship_csv(
        csv_body, reviewers=[alice], reviewees=[carol]
    )
    assert result.issues == []
    assert len(result.rows) == 1
    assert result.rows[0].reviewer_id == alice.id
    assert result.rows[0].reviewee_id == carol.id


def test_parse_empty_required_cells(db: Session) -> None:
    alice, _bob, carol, _dan = _seed(db)
    csv_body = (
        b"ReviewerEmail,RevieweeEmail\n"
        b",carol@example.edu\n"
        b"alice@example.edu,\n"
    )
    result = parse_relationship_csv(
        csv_body, reviewers=[alice], reviewees=[carol]
    )
    assert result.rows == []
    assert len(result.issues) == 2
    assert {issue.field for issue in result.issues} == {
        "ReviewerEmail",
        "RevieweeEmail",
    }
