"""Unit tests for ``app.services.extracts.relationships_extract`` —
Segment 12A-3 PR 1.

Mirror of ``test_reviewees_extract`` for the relationships shape.
The round-trip test pins the contract that the export feeds the
existing ``app.services.relationships.parse_relationship_csv``
importer (already shipped by 15D PR 1) without conversion.
"""

from __future__ import annotations

import csv
import io

from sqlalchemy.orm import Session

from app.db.models import (
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.services.extracts.relationships_extract import (
    HEADER,
    serialize_relationships,
)
from app.services.relationships import parse_relationship_csv


def _user(db: Session) -> User:
    user = User(email="alice@example.edu", display_name="Alice")
    db.add(user)
    db.flush()
    return user


def _session(db: Session, *, code: str = "rel") -> ReviewSession:
    user = _user(db)
    review_session = ReviewSession(
        name="Relationships", code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    return review_session


def _reviewer(
    db: Session, review_session: ReviewSession, *, name: str, email: str
) -> Reviewer:
    reviewer = Reviewer(
        session_id=review_session.id, name=name, email=email
    )
    db.add(reviewer)
    db.flush()
    return reviewer


def _reviewee(
    db: Session, review_session: ReviewSession, *, name: str, identifier: str
) -> Reviewee:
    reviewee = Reviewee(
        session_id=review_session.id,
        name=name,
        email_or_identifier=identifier,
    )
    db.add(reviewee)
    db.flush()
    return reviewee


def _add(
    db: Session,
    review_session: ReviewSession,
    *,
    reviewer: Reviewer,
    reviewee: Reviewee,
    status: str = "active",
    tag_1: str | None = None,
    tag_2: str | None = None,
    tag_3: str | None = None,
) -> None:
    db.add(
        Relationship(
            session_id=review_session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            status=status,
            tag_1=tag_1,
            tag_2=tag_2,
            tag_3=tag_3,
        )
    )
    db.flush()


def test_empty_session_emits_header_only(db: Session) -> None:
    review_session = _session(db, code="empty")
    rows = list(serialize_relationships(db, review_session))
    assert rows == [HEADER]


def test_per_row_shape_includes_pair_context_tags(db: Session) -> None:
    review_session = _session(db, code="shape")
    reviewer = _reviewer(
        db, review_session, name="Alex", email="alex@example.edu"
    )
    reviewee = _reviewee(
        db, review_session, name="Carol", identifier="carol@example.edu"
    )
    _add(
        db,
        review_session,
        reviewer=reviewer,
        reviewee=reviewee,
        tag_1="advisor",
        tag_3="cohort-a",
    )
    rows = list(serialize_relationships(db, review_session))
    assert rows[0] == HEADER
    assert rows[1] == (
        "alex@example.edu",
        "carol@example.edu",
        "advisor",
        "",
        "cohort-a",
        "active",
    )


def test_active_rows_lead_then_alphabetical(db: Session) -> None:
    review_session = _session(db, code="order")
    alex = _reviewer(
        db, review_session, name="Alex", email="alex@example.edu"
    )
    bob = _reviewer(db, review_session, name="Bob", email="bob@example.edu")
    carol = _reviewee(
        db, review_session, name="Carol", identifier="carol@example.edu"
    )
    dan = _reviewee(
        db, review_session, name="Dan", identifier="dan@example.edu"
    )

    _add(db, review_session, reviewer=bob, reviewee=carol)
    _add(
        db,
        review_session,
        reviewer=alex,
        reviewee=dan,
        status="inactive",
    )
    _add(db, review_session, reviewer=alex, reviewee=carol)

    body = list(serialize_relationships(db, review_session))[1:]
    # Active first (alex/carol, alex/dan? no - alex/dan is inactive),
    # then bob/carol (active), then inactive (alex/dan).
    assert [(r[0], r[1], r[5]) for r in body] == [
        ("alex@example.edu", "carol@example.edu", "active"),
        ("bob@example.edu", "carol@example.edu", "active"),
        ("alex@example.edu", "dan@example.edu", "inactive"),
    ]


def test_round_trip_through_existing_importer(db: Session) -> None:
    """Extract → parse via the existing relationships importer
    (shipped by 15D PR 1) → parsed rows match. Pins that the
    export CSV feeds the upload flow without conversion."""

    review_session = _session(db, code="rt")
    alex = _reviewer(
        db, review_session, name="Alex", email="alex@example.edu"
    )
    bob = _reviewer(db, review_session, name="Bob", email="bob@example.edu")
    carol = _reviewee(
        db, review_session, name="Carol", identifier="carol@example.edu"
    )
    dan = _reviewee(
        db, review_session, name="Dan", identifier="dan@example.edu"
    )
    _add(
        db,
        review_session,
        reviewer=alex,
        reviewee=carol,
        tag_1="advisor",
    )
    _add(
        db,
        review_session,
        reviewer=bob,
        reviewee=dan,
        tag_2="peer",
        status="inactive",
    )

    csv_bytes = _join_to_bytes(serialize_relationships(db, review_session))
    parse_result = parse_relationship_csv(
        csv_bytes,
        reviewers=[alex, bob],
        reviewees=[carol, dan],
    )
    assert parse_result.issues == []
    parsed = sorted(
        parse_result.rows, key=lambda r: (r.reviewer_id, r.reviewee_id)
    )
    assert [(r.reviewer_id, r.reviewee_id, r.status) for r in parsed] == [
        (alex.id, carol.id, "active"),
        (bob.id, dan.id, "inactive"),
    ]
    assert parsed[0].tag_1 == "advisor"
    assert parsed[1].tag_2 == "peer"


def _join_to_bytes(rows: object) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    for row in rows:  # type: ignore[union-attr]
        writer.writerow(row)
    return buf.getvalue().encode("utf-8")
