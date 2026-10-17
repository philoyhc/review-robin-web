"""Unit coverage for Segment 12C-1 PR 1 — `replace_assignments` honours
``sessions.self_reviews_active`` when writing self-review rows.

Two-layer model contract (post-15B Slice 1):

- The instrument's pinned ``SessionRuleSet`` decides whether
  self-review pairs are emitted by the generator at all.
- When self-review pairs ARE emitted, ``replace_assignments`` reads
  the session's ``self_reviews_active`` column to decide their
  ``include`` flag.

The 15D-retired ``includes=`` parameter is gone (manual-CSV
authoring deleted in 15D PR 7a); the per-pair operator override
now lives on the ``relationships`` row via the engine's
``pair_context`` predicate path.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import (
    Assignment,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionRuleSet,
    User,
)
from app.services import assignments
from app.services.instruments import ensure_default_instrument


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

    # Pin a Full-Matrix-shape rule to the default instrument so the
    # engine emits every reviewer × reviewee pair (including
    # self-reviews) — that's the population ``replace_assignments``
    # then writes through with the session-flag-aware include flag.
    full_matrix = SessionRuleSet(
        session_id=review_session.id,
        name="Full Matrix",
        description="",
        combinator="ALL_OF",
        exclude_self_reviews=False,
        seed=None,
        rules_json=[],
    )
    db.add(full_matrix)
    db.flush()
    default_inst = ensure_default_instrument(db, review_session)
    default_inst.rule_set_id = full_matrix.id
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

    user, review_session, *_ = _seed(db, self_reviews_active=False)

    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id="corr-off",
    )

    self_reviews = _self_review_assignments(db, review_session.id)
    assert len(self_reviews) == 1
    assert self_reviews[0].include is False

    rows = (
        db.query(Assignment)
        .filter(Assignment.session_id == review_session.id)
        .all()
    )
    non_self_includes = {
        a.include for a in rows if a not in self_reviews
    }
    assert non_self_includes == {True}


def test_self_review_row_active_when_session_flag_on(db: Session) -> None:
    """Default ``self_reviews_active=True`` keeps self-review rows
    ``include=True`` (matches pre-12C behaviour)."""

    user, review_session, *_ = _seed(db, self_reviews_active=True)

    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id="corr-on",
    )

    rows = (
        db.query(Assignment)
        .filter(Assignment.session_id == review_session.id)
        .all()
    )
    assert {a.include for a in rows} == {True}
