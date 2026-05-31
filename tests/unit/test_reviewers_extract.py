"""Unit tests for ``app.services.extracts.reviewers_extract`` —
Segment 12A-1 PR 2.

Covers the per-row shape, the active-then-inactive-then-by-name
ordering, the round-trip with the existing reviewer importer
(``app.services.csv_imports.parse_reviewer_csv``), and the
header-only payload on an empty session.
"""

from __future__ import annotations

import csv
import io

from sqlalchemy.orm import Session

from app.db.models import Reviewer, ReviewSession, User
from app.services.csv_imports import parse_reviewer_csv
from app.services.extracts.reviewers_extract import (
    HEADER,
    serialize_reviewers,
)


def _user(db: Session) -> User:
    user = User(email="alice@example.edu", display_name="Alice")
    db.add(user)
    db.flush()
    return user


def _session(db: Session, *, code: str = "rsv") -> ReviewSession:
    user = _user(db)
    review_session = ReviewSession(
        name="Reviewers", code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    return review_session


def _add(
    db: Session,
    review_session: ReviewSession,
    *,
    name: str,
    email: str,
    status: str = "active",
    profile_link: str | None = None,
    tag_1: str | None = None,
    tag_2: str | None = None,
    tag_3: str | None = None,
) -> None:
    db.add(
        Reviewer(
            session_id=review_session.id,
            name=name,
            email=email,
            status=status,
            profile_link=profile_link,
            tag_1=tag_1,
            tag_2=tag_2,
            tag_3=tag_3,
        )
    )
    db.flush()


def test_empty_session_emits_header_only(db: Session) -> None:
    review_session = _session(db, code="empty")
    rows = list(serialize_reviewers(db, review_session))
    assert rows == [HEADER]


def test_per_row_shape_matches_importer_columns(db: Session) -> None:
    review_session = _session(db, code="shape")
    _add(
        db,
        review_session,
        name="Alex Adams",
        email="alex@example.edu",
        tag_1="cohort-a",
        tag_2="2026",
        tag_3=None,
        profile_link="https://example.org/alex.png",
    )
    rows = list(serialize_reviewers(db, review_session))
    assert rows[0] == HEADER
    assert rows[1] == (
        "Alex Adams",
        "alex@example.edu",
        "cohort-a",
        "2026",
        "",
        "https://example.org/alex.png",
    )


def test_per_row_shape_empty_profile_link_yields_blank(
    db: Session,
) -> None:
    review_session = _session(db, code="shape-blank")
    _add(
        db,
        review_session,
        name="Bea",
        email="bea@example.edu",
    )
    rows = list(serialize_reviewers(db, review_session))
    assert rows[1] == ("Bea", "bea@example.edu", "", "", "", "")


def test_active_rows_lead_then_alphabetical(db: Session) -> None:
    review_session = _session(db, code="order")
    _add(db, review_session, name="Zoe", email="zoe@example.edu")
    _add(
        db,
        review_session,
        name="Mallory",
        email="mallory@example.edu",
        status="inactive",
    )
    _add(db, review_session, name="Bob", email="bob@example.edu")

    body = list(serialize_reviewers(db, review_session))[1:]
    assert [r[0] for r in body] == ["Bob", "Zoe", "Mallory"]


def test_round_trip_through_existing_importer(db: Session) -> None:
    """Extract from session A → upload to session B via the
    existing reviewer importer → assert the parsed rows match A's
    roster verbatim. Pins the contract that the export feeds the
    upload flow without conversion."""

    a = _session(db, code="rt-a")
    _add(
        db,
        a,
        name="Alex Adams",
        email="alex@example.edu",
        tag_1="cohort-a",
        tag_2="2026",
        profile_link="https://example.org/alex.png",
    )
    _add(db, a, name="Bob Brown", email="bob@example.edu", tag_3="lead")

    csv_bytes = _join_to_bytes(serialize_reviewers(db, a))
    parse_result = parse_reviewer_csv(csv_bytes)
    assert parse_result.issues == []
    parsed = sorted(parse_result.rows, key=lambda r: r.email)
    assert [r.name for r in parsed] == ["Alex Adams", "Bob Brown"]
    assert [r.email for r in parsed] == ["alex@example.edu", "bob@example.edu"]
    assert [r.tag_1 for r in parsed] == ["cohort-a", None]
    assert [r.tag_3 for r in parsed] == [None, "lead"]
    assert [r.profile_link for r in parsed] == [
        "https://example.org/alex.png",
        None,
    ]


def _join_to_bytes(rows: object) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:  # type: ignore[union-attr]
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")
