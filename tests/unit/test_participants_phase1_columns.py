"""Unit tests for the participant-model Phase 1 column additions
on existing tables — pins ``reviewers.profile_link``,
``reviewees.results_acknowledged_at``, and the two session-level
feature toggles before Phase 2 / Phase 3 slices read them.

See ``guide/archive/participant_model_upgrade.md`` rows S7, S8, S9, S11.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import Reviewee, Reviewer, ReviewSession, User


def _session(db: Session, *, code: str = "p1") -> ReviewSession:
    user = User(email=f"{code}@x.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="P1",
        code=code,
        created_by_user_id=user.id,
        assignment_mode="manual",
    )
    db.add(review_session)
    db.flush()
    return review_session


def test_session_feature_toggles_default_false(db: Session) -> None:
    review_session = _session(db)
    db.commit()
    refetched = db.get(ReviewSession, review_session.id)
    assert refetched is not None
    assert refetched.relationships_enabled is False
    assert refetched.observers_enabled is False


def test_session_feature_toggles_round_trip(db: Session) -> None:
    review_session = _session(db)
    review_session.relationships_enabled = True
    review_session.observers_enabled = True
    db.commit()
    refetched = db.get(ReviewSession, review_session.id)
    assert refetched is not None
    assert refetched.relationships_enabled is True
    assert refetched.observers_enabled is True


def test_reviewer_profile_link_optional(db: Session) -> None:
    review_session = _session(db)
    reviewer = Reviewer(
        session_id=review_session.id,
        name="Rev",
        email="rev@example.org",
    )
    db.add(reviewer)
    db.commit()
    assert reviewer.profile_link is None

    reviewer.profile_link = "https://example.org/rev"
    db.commit()
    refetched = db.get(Reviewer, reviewer.id)
    assert refetched is not None
    assert refetched.profile_link == "https://example.org/rev"


def test_reviewee_results_acknowledged_at_optional(db: Session) -> None:
    review_session = _session(db)
    reviewee = Reviewee(
        session_id=review_session.id,
        name="Subj",
        email_or_identifier="subj@example.org",
    )
    db.add(reviewee)
    db.commit()
    assert reviewee.results_acknowledged_at is None

    stamp = datetime(2026, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    reviewee.results_acknowledged_at = stamp
    db.commit()
    refetched = db.get(Reviewee, reviewee.id)
    assert refetched is not None
    assert refetched.results_acknowledged_at == stamp
