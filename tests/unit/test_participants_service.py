"""Unit tests for ``app/services/participants.py`` — the
participant-side predicates the route guards and surfaces call
into. Covers ``is_email_identified`` (W1). The earlier
``sessions_for_user`` / ``ParticipantSession`` shape stub retired
2026-06-01 alongside the cross-role lobby cleanup (L1 from the
participant-model remainder doc) — W18 built the union inline in
``_dashboard.py`` and never consumed the stub. See
``guide/archive/participant_model_upgrade.md`` §3.2 (and Appendix A
row W1).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Reviewee, ReviewSession, User
from app.services import participants


def _session(db: Session, *, code: str = "psvc") -> ReviewSession:
    user = User(email=f"{code}@x.edu", display_name="Op")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="P",
        code=code,
        created_by_user_id=user.id,
        assignment_mode="manual",
    )
    db.add(review_session)
    db.flush()
    return review_session


def _reviewee(
    db: Session, *, session: ReviewSession, identifier: str
) -> Reviewee:
    r = Reviewee(
        session_id=session.id,
        name="Subj",
        email_or_identifier=identifier,
    )
    db.add(r)
    db.flush()
    return r


def test_is_email_identified_accepts_valid_email(db: Session) -> None:
    s = _session(db)
    r = _reviewee(db, session=s, identifier="alice@example.org")
    assert participants.is_email_identified(r) is True


def test_is_email_identified_rejects_non_email_identifier(
    db: Session,
) -> None:
    s = _session(db)
    for ident in ("anon-007", "subject_42", "no-at-sign-here.com"):
        r = _reviewee(db, session=s, identifier=ident)
        assert participants.is_email_identified(r) is False, ident


def test_is_email_identified_rejects_malformed_email(db: Session) -> None:
    s = _session(db)
    for ident in (
        "missing@tld",
        "@example.org",
        "alice@",
        "two@@example.org",
        "alice@example .org",
    ):
        r = _reviewee(db, session=s, identifier=ident)
        assert participants.is_email_identified(r) is False, ident


def test_is_email_identified_rejects_whitespace_only(db: Session) -> None:
    # Reviewee.email_or_identifier is NOT NULL at the DB layer; the
    # service layer normalises before persist. The helper still
    # needs to handle the edge cases — exercise via a fresh, not-yet-
    # flushed Reviewee so we can carry whitespace.
    r = Reviewee(
        session_id=1, name="X", email_or_identifier="   "
    )
    assert participants.is_email_identified(r) is False


def test_is_email_identified_trims_surrounding_whitespace(
    db: Session,
) -> None:
    r = Reviewee(
        session_id=1, name="X", email_or_identifier="  bob@example.org  "
    )
    assert participants.is_email_identified(r) is True

