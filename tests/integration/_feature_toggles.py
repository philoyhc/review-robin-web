"""Shared test helpers for the participant-model per-session
feature toggles (``guide/archive/participant_model_upgrade.md`` §3.8).

The toggles default to ``False`` so the Relationships tab + route
guard ship hidden until an operator opts in via the User
interface settings card on Session Edit Details. Tests that
exercise the Relationships routes call ``enable_relationships``
on their freshly-made session to put the flag back to ``True``
without going through the form.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import ReviewSession


def enable_relationships(db: Session, review_session: ReviewSession) -> ReviewSession:
    """Flip ``relationships_enabled`` to True and commit.

    Returns the session for chaining.
    """
    if not review_session.relationships_enabled:
        review_session.relationships_enabled = True
        db.commit()
        db.refresh(review_session)
    return review_session


def enable_observers(db: Session, review_session: ReviewSession) -> ReviewSession:
    """Symmetric helper for the observers toggle. Used once the
    Observer tab + route guard ships in a follow-up PR."""
    if not review_session.observers_enabled:
        review_session.observers_enabled = True
        db.commit()
        db.refresh(review_session)
    return review_session
