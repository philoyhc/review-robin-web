"""Unit coverage for Segment 12C-1 PR 1 — `replace_assignments` honours
``sessions.self_reviews_active`` when writing self-review rows.

Two-layer model contract:

- The RuleSet (or the legacy full-matrix toggle) decides whether
  self-review pairs are emitted by the generator at all.
- When self-review pairs ARE emitted, ``replace_assignments`` reads
  the session's ``self_reviews_active`` column to decide their
  ``include`` flag.

Manual-CSV path is unaffected: when an explicit ``includes`` list is
passed (the manual-CSV save path) the operator-typed value wins,
regardless of what the session-level column says.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Assignment, Reviewee, Reviewer, ReviewSession, User
from app.schemas.assignments import AssignmentMode
from app.services import assignments


def _seed(db: Session, *, self_reviews_active: bool) -> tuple[
    User, ReviewSession, Reviewer, Reviewer, Reviewee, Reviewee
]:
    user = User(email="op@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Spring",
        code=f"sra-{self_reviews_active}",
        created_by_user_id=user.id,
        self_reviews_active=self_reviews_active,
    )
    db.add(review_session)
    db.flush()
    alice_r = Reviewer(
        session_id=review_session.id, name="Alice", email="alice@example.edu"
    )
    bob_r = Reviewer(
        session_id=review_session.id, name="Bob", email="bob@example.edu"
    )
    alice_e = Reviewee(
        session_id=review_session.id,
        name="Alice",
        email_or_identifier="alice@example.edu",
    )
    carol_e = Reviewee(
        session_id=review_session.id,
        name="Carol",
        email_or_identifier="carol@example.edu",
    )
    db.add_all([alice_r, bob_r, alice_e, carol_e])
    db.flush()
    return user, review_session, alice_r, bob_r, alice_e, carol_e


def _self_review_assignments(
    db: Session, session_id: int
) -> list[Assignment]:
    rows = (
        db.query(Assignment, Reviewer, Reviewee)
        .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
        .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        .filter(Assignment.session_id == session_id)
        .all()
    )
    return [a for a, r, e in rows if assignments.is_self_review(r, e)]


def test_self_review_row_inactive_when_session_flag_off(db: Session) -> None:
    """``self_reviews_active=False`` flips self-review rows' ``include``
    to ``False``; non-self-review rows stay ``True``."""

    user, review_session, alice_r, bob_r, alice_e, carol_e = _seed(
        db, self_reviews_active=False
    )

    pairs = [(alice_r, alice_e), (alice_r, carol_e), (bob_r, alice_e)]
    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        pairs=pairs,
        mode=AssignmentMode.rule_based,
        correlation_id="corr-off",
    )

    self_reviews = _self_review_assignments(db, review_session.id)
    assert len(self_reviews) == 1
    assert self_reviews[0].include is False

    non_self = (
        db.query(Assignment).filter(Assignment.session_id == review_session.id).all()
    )
    non_self_includes = {
        a.include
        for a in non_self
        if a not in self_reviews
    }
    assert non_self_includes == {True}


def test_self_review_row_active_when_session_flag_on(db: Session) -> None:
    """Default ``self_reviews_active=True`` keeps self-review rows
    ``include=True`` (matches pre-12C behaviour for unaffected callers)."""

    user, review_session, alice_r, bob_r, alice_e, carol_e = _seed(
        db, self_reviews_active=True
    )

    pairs = [(alice_r, alice_e), (bob_r, carol_e)]
    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        pairs=pairs,
        mode=AssignmentMode.rule_based,
        correlation_id="corr-on",
    )

    rows = (
        db.query(Assignment).filter(Assignment.session_id == review_session.id).all()
    )
    assert {a.include for a in rows} == {True}


def test_explicit_includes_win_over_session_flag(db: Session) -> None:
    """The manual-CSV save path passes an explicit ``includes`` list;
    operator-typed values must beat the session-level default even
    when the pair is a self-review and the session flag is off."""

    user, review_session, alice_r, _bob_r, alice_e, carol_e = _seed(
        db, self_reviews_active=False
    )

    pairs = [(alice_r, alice_e), (alice_r, carol_e)]
    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        pairs=pairs,
        mode=AssignmentMode.manual,
        correlation_id="corr-manual",
        includes=[True, False],
    )

    rows = (
        db.query(Assignment, Reviewer, Reviewee)
        .join(Reviewer, Assignment.reviewer_id == Reviewer.id)
        .join(Reviewee, Assignment.reviewee_id == Reviewee.id)
        .filter(Assignment.session_id == review_session.id)
        .all()
    )
    by_pair = {
        (r.email, e.email_or_identifier): a.include for a, r, e in rows
    }
    assert by_pair[("alice@example.edu", "alice@example.edu")] is True
    assert by_pair[("alice@example.edu", "carol@example.edu")] is False
