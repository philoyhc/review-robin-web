"""Unit tests for ``app.services.extracts.reviewees_extract`` —
Segment 12A-1 PR 2.

Mirror of ``test_reviewers_extract`` for the reviewee shape,
including the ``PhotoLink`` column matching the importer at
``app.services.csv_imports.parse_reviewee_csv``.
"""

from __future__ import annotations

import csv
import io

from sqlalchemy.orm import Session

from app.db.models import Reviewee, ReviewSession, User
from app.services.csv_imports import parse_reviewee_csv
from app.services.extracts.reviewees_extract import (
    HEADER,
    serialize_reviewees,
)


def _user(db: Session) -> User:
    user = User(email="alice@example.edu", display_name="Alice")
    db.add(user)
    db.flush()
    return user


def _session(db: Session, *, code: str = "rev") -> ReviewSession:
    user = _user(db)
    review_session = ReviewSession(
        name="Reviewees", code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    return review_session


def _add(
    db: Session,
    review_session: ReviewSession,
    *,
    name: str,
    identifier: str,
    status: str = "active",
    tag_1: str | None = None,
    tag_2: str | None = None,
    tag_3: str | None = None,
    profile_link: str | None = None,
) -> None:
    db.add(
        Reviewee(
            session_id=review_session.id,
            name=name,
            email_or_identifier=identifier,
            status=status,
            tag_1=tag_1,
            tag_2=tag_2,
            tag_3=tag_3,
            profile_link=profile_link,
        )
    )
    db.flush()


def test_empty_session_emits_header_only(db: Session) -> None:
    review_session = _session(db, code="empty")
    rows = list(serialize_reviewees(db, review_session))
    assert rows == [HEADER]


def test_per_row_shape_includes_photo_link(db: Session) -> None:
    review_session = _session(db, code="shape")
    _add(
        db,
        review_session,
        name="Carol Carter",
        identifier="carol@example.edu",
        tag_1="design",
        tag_3=None,
        profile_link="https://example.edu/carol.jpg",
    )
    rows = list(serialize_reviewees(db, review_session))
    assert rows[0] == HEADER
    assert rows[1] == (
        "Carol Carter",
        "carol@example.edu",
        "design",
        "",
        "",
        "https://example.edu/carol.jpg",
    )


def test_active_rows_lead_then_alphabetical(db: Session) -> None:
    review_session = _session(db, code="order")
    _add(db, review_session, name="Zoe", identifier="zoe@example.edu")
    _add(
        db,
        review_session,
        name="Mallory",
        identifier="mallory@example.edu",
        status="inactive",
    )
    _add(db, review_session, name="Bob", identifier="bob@example.edu")

    body = list(serialize_reviewees(db, review_session))[1:]
    assert [r[0] for r in body] == ["Bob", "Zoe", "Mallory"]


def test_round_trip_through_existing_importer(db: Session) -> None:
    """Extract → upload → parsed rows match. Pins the contract
    that export feeds the upload flow without conversion. The
    ``PhotoLink`` header lines up with
    ``parse_reviewee_csv:336`` — a rename on either side fails
    this test."""

    a = _session(db, code="rt-a")
    _add(
        db,
        a,
        name="Carol Carter",
        identifier="carol@example.edu",
        tag_1="design",
        profile_link="https://example.edu/carol.jpg",
    )
    _add(db, a, name="Dan Doyle", identifier="dan@example.edu", tag_2="dev")

    csv_bytes = _join_to_bytes(serialize_reviewees(db, a))
    parse_result = parse_reviewee_csv(csv_bytes)
    assert parse_result.issues == []
    parsed = sorted(parse_result.rows, key=lambda r: r.email_or_identifier)
    assert [r.name for r in parsed] == ["Carol Carter", "Dan Doyle"]
    assert [r.email_or_identifier for r in parsed] == [
        "carol@example.edu",
        "dan@example.edu",
    ]
    assert parsed[0].profile_link == "https://example.edu/carol.jpg"
    assert parsed[0].tag_1 == "design"
    assert parsed[1].tag_2 == "dev"


def _join_to_bytes(rows: object) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:  # type: ignore[union-attr]
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")
