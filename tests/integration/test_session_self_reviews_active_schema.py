"""Schema-level coverage for Segment 13E PR 1 — ``sessions.self_reviews_active``.

Pins the per-session activator flag's contract for Segment 12C-1 to
consume:

- New sessions land with the flag set to ``TRUE`` via the server
  default (the post-12C "self-reviews on by default" stance).
- Operator-written ``False`` round-trips cleanly.

The column sits inert until 12C-1 PR 1 wires the generation-path
read and 12C-1 PR 3 wires the bulk-toggle write; this file is the
schema gate that lets that work land without further Alembic
churn.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User


def _make_user(db: Session, email: str) -> User:
    user = User(email=email, display_name=email.split("@", 1)[0])
    db.add(user)
    db.flush()
    return user


def test_default_true_on_new_session(db: Session) -> None:
    """A session created without explicitly setting the flag picks up
    the server default (``TRUE``)."""

    owner = _make_user(db, "op-default@example.edu")
    review_session = ReviewSession(
        name="Default", code="sra-default", created_by_user_id=owner.id
    )
    db.add(review_session)
    db.flush()
    db.refresh(review_session)

    assert review_session.self_reviews_active is True


def test_explicit_false_round_trip(db: Session) -> None:
    """Operator-written ``False`` persists and reads back."""

    owner = _make_user(db, "op-false@example.edu")
    review_session = ReviewSession(
        name="Off",
        code="sra-off",
        created_by_user_id=owner.id,
        self_reviews_active=False,
    )
    db.add(review_session)
    db.flush()

    fetched = db.execute(
        select(ReviewSession).where(ReviewSession.id == review_session.id)
    ).scalar_one()
    assert fetched.self_reviews_active is False
