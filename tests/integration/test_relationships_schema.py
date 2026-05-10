"""Schema-level coverage for Segment 13E PR 2 — ``relationships``.

Pins the per-pair-attributes table contract for Segment 15D to
consume:

- Round-trip insert + read with default ``status="active"``.
- ``UNIQUE (session_id, reviewer_id, reviewee_id)`` enforced.
- ``ON DELETE CASCADE`` on each of session / reviewer / reviewee
  reaps the rows when the owning entity is deleted.
- The table starts empty on every deployment running the
  migration.

The table sits inert until 15D PR 1 introduces the per-entity
importer + serializer; this file is the schema gate that lets
that work land without further Alembic churn.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Relationship,
    ReviewSession,
    Reviewee,
    Reviewer,
    User,
)


def _make_user(db: Session, email: str) -> User:
    user = User(email=email, display_name=email.split("@", 1)[0])
    db.add(user)
    db.flush()
    return user


def _make_session(db: Session, code: str) -> ReviewSession:
    owner = _make_user(db, f"op-{code}@example.edu")
    review_session = ReviewSession(
        name=code.title(), code=code, created_by_user_id=owner.id
    )
    db.add(review_session)
    db.flush()
    return review_session


def _make_reviewer(
    db: Session, session: ReviewSession, email: str
) -> Reviewer:
    reviewer = Reviewer(
        session_id=session.id,
        name=email.split("@", 1)[0],
        email=email,
    )
    db.add(reviewer)
    db.flush()
    return reviewer


def _make_reviewee(
    db: Session, session: ReviewSession, identifier: str
) -> Reviewee:
    reviewee = Reviewee(
        session_id=session.id,
        name=identifier.split("@", 1)[0],
        email_or_identifier=identifier,
    )
    db.add(reviewee)
    db.flush()
    return reviewee


def test_table_starts_empty(db: Session) -> None:
    """The migration creates the table with no rows."""

    rows = db.execute(select(Relationship)).scalars().all()
    assert rows == []


def test_round_trip(db: Session) -> None:
    """Insert + read; ``status`` server-defaults to ``active``,
    tag columns persist nullable values."""

    review_session = _make_session(db, "rel-rt")
    reviewer = _make_reviewer(db, review_session, "rev@example.edu")
    reviewee = _make_reviewee(db, review_session, "ree@example.edu")
    row = Relationship(
        session_id=review_session.id,
        reviewer_id=reviewer.id,
        reviewee_id=reviewee.id,
        tag_1="cohort-A",
        tag_2=None,
        tag_3="lead",
    )
    db.add(row)
    db.flush()
    db.refresh(row)

    fetched = db.execute(
        select(Relationship).where(Relationship.id == row.id)
    ).scalar_one()
    assert fetched.session_id == review_session.id
    assert fetched.reviewer_id == reviewer.id
    assert fetched.reviewee_id == reviewee.id
    assert fetched.tag_1 == "cohort-A"
    assert fetched.tag_2 is None
    assert fetched.tag_3 == "lead"
    assert fetched.status == "active"


def test_unique_per_pair_in_session(db: Session) -> None:
    """Two rows with the same ``(session, reviewer, reviewee)`` tuple
    violate ``uq_relationships_session_reviewer_reviewee``."""

    review_session = _make_session(db, "rel-uq")
    reviewer = _make_reviewer(db, review_session, "rev@example.edu")
    reviewee = _make_reviewee(db, review_session, "ree@example.edu")
    db.add(
        Relationship(
            session_id=review_session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
        )
    )
    db.flush()

    db.add(
        Relationship(
            session_id=review_session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
        )
    )
    with pytest.raises(IntegrityError):
        db.flush()


def test_cascade_on_session_delete(db: Session) -> None:
    """Deleting the owning session reaps every relationship row."""

    review_session = _make_session(db, "rel-csess")
    reviewer = _make_reviewer(db, review_session, "rev@example.edu")
    reviewee = _make_reviewee(db, review_session, "ree@example.edu")
    db.add(
        Relationship(
            session_id=review_session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
        )
    )
    db.flush()
    session_id = review_session.id

    db.delete(review_session)
    db.flush()

    remaining = db.execute(
        select(Relationship).where(Relationship.session_id == session_id)
    ).scalars().all()
    assert remaining == []


def test_cascade_on_reviewer_delete(db: Session) -> None:
    """Deleting a reviewer reaps the relationships referencing them."""

    review_session = _make_session(db, "rel-crev")
    reviewer = _make_reviewer(db, review_session, "rev@example.edu")
    reviewee = _make_reviewee(db, review_session, "ree@example.edu")
    db.add(
        Relationship(
            session_id=review_session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
        )
    )
    db.flush()
    reviewer_id = reviewer.id

    db.delete(reviewer)
    db.flush()

    remaining = db.execute(
        select(Relationship).where(Relationship.reviewer_id == reviewer_id)
    ).scalars().all()
    assert remaining == []


def test_cascade_on_reviewee_delete(db: Session) -> None:
    """Deleting a reviewee reaps the relationships referencing them."""

    review_session = _make_session(db, "rel-cree")
    reviewer = _make_reviewer(db, review_session, "rev@example.edu")
    reviewee = _make_reviewee(db, review_session, "ree@example.edu")
    db.add(
        Relationship(
            session_id=review_session.id,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
        )
    )
    db.flush()
    reviewee_id = reviewee.id

    db.delete(reviewee)
    db.flush()

    remaining = db.execute(
        select(Relationship).where(Relationship.reviewee_id == reviewee_id)
    ).scalars().all()
    assert remaining == []
