"""PR 4 of the ``guide/self_review_consolidate.md`` slice —
post-regenerate continuous-gate invariant.

The invariant pair is:

* :func:`assignments.verify_self_review_classification` — read-
  only: returns the list of ``(assignment_id, stored, expected)``
  drift tuples.
* :func:`assignments.replace_assignments` calls verify after its
  own recompute. In test envs drift raises ``AssertionError``;
  in production it logs + auto-corrects via
  :func:`assignments.recompute_self_review_classification`.

Tests cover:

* Verify returns empty on a freshly-regenerated session
  (column matches the canonical rule on every row).
* Verify detects manually-induced drift.
* Regenerate's strict-mode assert fires when a drift is staged
  pre-regenerate-without-recompute (synthetic ladder test).
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


def _seed_self_review_session(
    db: Session, *, code: str
) -> tuple[User, ReviewSession, Reviewer, Reviewee]:
    user = User(email=f"op-{code}@example.edu")
    db.add(user)
    db.flush()
    review_session = ReviewSession(
        name="Spring",
        code=code,
        created_by_user_id=user.id,
    )
    db.add(review_session)
    db.flush()
    alice_r = Reviewer(
        session_id=review_session.id, name="Alice", email="alice@example.edu"
    )
    alice_e = Reviewee(
        session_id=review_session.id,
        name="Alice",
        email_or_identifier="alice@example.edu",
    )
    db.add_all([alice_r, alice_e])
    db.flush()
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
    instrument = ensure_default_instrument(db, review_session)
    instrument.rule_set_id = full_matrix.id
    db.flush()
    return user, review_session, alice_r, alice_e


# --------------------------------------------------------------------------- #
# verify_self_review_classification
# --------------------------------------------------------------------------- #


def test_verify_empty_on_freshly_regenerated_session(db: Session) -> None:
    user, review_session, _alice_r, _alice_e = _seed_self_review_session(
        db, code="verify-clean"
    )
    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id="verify-clean",
    )
    drift = assignments.verify_self_review_classification(
        db, session_id=review_session.id
    )
    assert drift == []


def test_verify_detects_manually_induced_drift(db: Session) -> None:
    """If the column gets out of sync with the canonical rule (e.g.
    via a future buggy write path that skips the recompute hook),
    ``verify`` surfaces the drift in ``(id, stored, expected)``
    triples."""
    user, review_session, alice_r, alice_e = _seed_self_review_session(
        db, code="verify-drift"
    )
    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id="verify-drift-regen",
    )
    self_row = (
        db.query(Assignment)
        .filter(
            Assignment.reviewer_id == alice_r.id,
            Assignment.reviewee_id == alice_e.id,
        )
        .one()
    )
    assert self_row.is_self_review is True

    # Stomp the column to a wrong value — simulates a future write
    # path that misses the recompute hook.
    self_row.is_self_review = False
    db.flush()

    drift = assignments.verify_self_review_classification(
        db, session_id=review_session.id
    )
    assert drift == [(self_row.id, False, True)]


def test_verify_returns_empty_for_session_with_no_assignments(
    db: Session,
) -> None:
    """No assignments → no drift to report."""
    _, review_session, _, _ = _seed_self_review_session(
        db, code="verify-empty"
    )
    # Skip the regenerate; no assignments materialised.
    drift = assignments.verify_self_review_classification(
        db, session_id=review_session.id
    )
    assert drift == []


# --------------------------------------------------------------------------- #
# Regenerate strict-mode gate
# --------------------------------------------------------------------------- #


def test_regenerate_strict_mode_raises_on_persistent_drift(
    db: Session, monkeypatch
) -> None:
    """Synthetic test: force the recompute helper to no-op so the
    invariant catches the drift the recompute would otherwise fix
    in production. In test env this raises ``AssertionError``,
    matching the strict-mode contract in
    ``guide/self_review_consolidate.md`` PR 4."""
    user, review_session, alice_r, alice_e = _seed_self_review_session(
        db, code="strict-drift"
    )
    # First regenerate cleanly so a self-review row exists.
    assignments.replace_assignments(
        db,
        review_session=review_session,
        user=user,
        correlation_id="strict-pre",
    )
    self_row = (
        db.query(Assignment)
        .filter(
            Assignment.reviewer_id == alice_r.id,
            Assignment.reviewer_id == alice_r.id,
            Assignment.reviewee_id == alice_e.id,
        )
        .one()
    )
    assert self_row.is_self_review is True

    # Stage drift, then stub the recompute helper so the next
    # regenerate's recompute-then-verify pipeline lets the drift
    # survive to the verify step.
    self_row.is_self_review = False
    db.flush()
    db.commit()

    def _noop_recompute(*_args, **_kwargs) -> int:
        return 0

    monkeypatch.setattr(
        assignments, "recompute_self_review_classification", _noop_recompute
    )
    # Also patch the in-module reference the regenerate body uses.
    import app.services.assignments as assignments_module

    monkeypatch.setattr(
        assignments_module,
        "recompute_self_review_classification",
        _noop_recompute,
    )

    try:
        assignments.replace_assignments(
            db,
            review_session=review_session,
            user=user,
            correlation_id="strict-trigger",
        )
    except AssertionError as exc:
        assert "Self-review classification drift" in str(exc)
        assert str(review_session.id) in str(exc)
    else:
        raise AssertionError(
            "Expected strict-mode AssertionError on drift, none raised."
        )
