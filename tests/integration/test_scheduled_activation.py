"""Coverage for the Segment 18G Part 1 scheduled-activation trigger.

The trigger is invoked from the lazy observer
(``observe_scheduled_events``) on operator GETs to session-related
pages. These tests call the trigger directly via the observer entry
point and assert on the resulting status flip + audit log.

Per the Part 1 plan section in
``guide/segment_18G_scheduled_events.md``:

- Happy path: validated session, scheduled time has passed → fires
  ``activate_session``; status flips to ``ready``; the resulting
  ``session.activated`` audit event carries ``context.trigger=scheduled``;
  ``scheduled_activate_at`` is cleared.
- Not-yet-due: scheduled time in the future → no-op.
- Precondition miss (still ``draft``): one-shot skip, audit emitted,
  schedule cleared.
- Transient transition failure: ``activate_session`` raises a
  non-precondition error → retry audit emitted; schedule retained.
- 3 retries → 4th attempt fires ``failed_persistent``; schedule
  cleared.
- Idempotency: a second observer call on an already-cleared schedule
  is a no-op (covers the SELECT FOR UPDATE + idempotency-check
  pattern).
- ``context.trigger`` provenance is also recorded for the existing
  manual-activate path (``operator``), guarding against regression
  of the default-arg behaviour.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    Reviewee,
    Reviewer,
    ReviewSession,
    User,
)
from app.schemas.sessions import SessionCreate
from app.services import scheduled_events
from app.services import session_lifecycle as lifecycle
from app.services import sessions as sessions_service
from ._full_matrix import pin_full_matrix_on_all_instruments


# --------------------------------------------------------------------------- #
# Fixtures                                                                    #
# --------------------------------------------------------------------------- #


def _make_validated_session(db: Session, code: str) -> ReviewSession:
    """Create a session that can be activated.

    Goes through ``sessions.create_session`` so seeded RuleSets
    materialise (the Full Matrix rule needs to exist for
    Instrument.rule_set_id pinning to satisfy the lifecycle gate),
    then attaches a roster + pinned rule + flips status to
    ``validated`` (bypassing the validate flow since the trigger
    reads status, not audit history).
    """
    op = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(op)
    db.flush()

    payload = SessionCreate(
        name=code.title(),
        code=code,
        description="test",
        deadline=None,
        help_contact=None,
    )
    review_session = sessions_service.create_session(db, user=op, payload=payload)

    reviewer = Reviewer(
        session_id=review_session.id,
        name="Alice",
        email=f"alice-{code}@example.edu",
    )
    reviewee = Reviewee(
        session_id=review_session.id,
        name="Carol",
        email_or_identifier=f"carol-{code}@example.edu",
    )
    db.add_all([reviewer, reviewee])
    db.flush()

    # Wave 5 PR 5.2 — lazily materialise the Full Matrix
    # ``session_rule_sets`` row (auto-seed retired).
    pin_full_matrix_on_all_instruments(db, review_session.id)

    review_session.status = lifecycle.SessionStatus.validated.value
    db.flush()
    db.commit()
    db.refresh(review_session)
    return review_session


def _audit_types(db: Session, session: ReviewSession) -> list[str]:
    rows = db.execute(
        select(AuditEvent.event_type)
        .where(AuditEvent.session_id == session.id)
        .order_by(AuditEvent.id)
    ).scalars().all()
    return list(rows)


def _audit_rows(db: Session, session: ReviewSession, event_type: str) -> list[AuditEvent]:
    return list(
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.session_id == session.id)
            .where(AuditEvent.event_type == event_type)
            .order_by(AuditEvent.id)
        ).scalars()
    )


# --------------------------------------------------------------------------- #
# Happy path                                                                  #
# --------------------------------------------------------------------------- #


def test_observer_fires_scheduled_activation_when_due(db: Session) -> None:
    """Validated session + scheduled_activate_at in the past + observer
    invocation → status flips to ready, schedule is cleared, audit
    carries context.trigger=scheduled."""
    review_session = _make_validated_session(db, "fire-happy")
    review_session.scheduled_activate_at = datetime(
        2099, 1, 1, 9, 0, tzinfo=timezone.utc
    )
    db.flush()
    db.commit()

    # Fire with now-past-the-schedule
    later = datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc)
    scheduled_events.observe_scheduled_events(db, review_session, now=later)
    db.refresh(review_session)

    assert review_session.status == lifecycle.SessionStatus.ready.value
    assert review_session.scheduled_activate_at is None

    activations = _audit_rows(db, review_session, "session.activated")
    assert len(activations) == 1
    detail = activations[0].detail
    assert detail["context"]["trigger"] == "scheduled"


def test_observer_no_op_when_schedule_in_future(db: Session) -> None:
    """Scheduled time hasn't arrived yet → trigger does nothing."""
    review_session = _make_validated_session(db, "future")
    future = datetime(2099, 12, 31, 9, 0, tzinfo=timezone.utc)
    review_session.scheduled_activate_at = future
    db.flush()
    db.commit()

    earlier = datetime(2099, 1, 1, tzinfo=timezone.utc)
    scheduled_events.observe_scheduled_events(db, review_session, now=earlier)
    db.refresh(review_session)

    assert review_session.status == lifecycle.SessionStatus.validated.value
    # SQLite drops tzinfo on round-trip; compare via _ensure_aware_utc
    assert review_session.scheduled_activate_at is not None
    assert (
        scheduled_events._ensure_aware_utc(review_session.scheduled_activate_at)
        == future
    )
    assert "session.activated" not in _audit_types(db, review_session)


def test_observer_no_op_when_schedule_unset(db: Session) -> None:
    """scheduled_activate_at = None → trigger does nothing."""
    review_session = _make_validated_session(db, "unset")
    assert review_session.scheduled_activate_at is None

    later = datetime(2099, 1, 1, tzinfo=timezone.utc)
    scheduled_events.observe_scheduled_events(db, review_session, now=later)
    db.refresh(review_session)

    assert review_session.status == lifecycle.SessionStatus.validated.value
    assert "session.activated" not in _audit_types(db, review_session)


# --------------------------------------------------------------------------- #
# Precondition skip path                                                      #
# --------------------------------------------------------------------------- #


def test_observer_skips_when_session_not_validated(db: Session) -> None:
    """Schedule fires while session is still draft → one-shot skip:
    audit emitted with reason=not_validated; schedule cleared."""
    review_session = _make_validated_session(db, "skip-not-val")
    # Revert to draft to simulate "operator edited setup after scheduling"
    review_session.status = lifecycle.SessionStatus.draft.value
    review_session.scheduled_activate_at = datetime(
        2099, 1, 1, 9, 0, tzinfo=timezone.utc
    )
    db.flush()
    db.commit()

    later = datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc)
    scheduled_events.observe_scheduled_events(db, review_session, now=later)
    db.refresh(review_session)

    assert review_session.status == lifecycle.SessionStatus.draft.value
    assert review_session.scheduled_activate_at is None
    skips = _audit_rows(db, review_session, "session.scheduled_activation_skipped")
    assert len(skips) == 1
    detail = skips[0].detail
    assert detail["reason"] == "not_validated"
    assert "scheduled_at" in detail["context"]
    assert "session.activated" not in _audit_types(db, review_session)


# --------------------------------------------------------------------------- #
# Concurrency / idempotency                                                   #
# --------------------------------------------------------------------------- #


def test_observer_idempotent_on_already_cleared_schedule(db: Session) -> None:
    """A second observer call after a successful fire is a no-op
    (the lock + idempotency check returns early when
    scheduled_activate_at is already None)."""
    review_session = _make_validated_session(db, "idempotent")
    review_session.scheduled_activate_at = datetime(
        2099, 1, 1, 9, 0, tzinfo=timezone.utc
    )
    db.flush()
    db.commit()

    later = datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc)
    scheduled_events.observe_scheduled_events(db, review_session, now=later)
    db.refresh(review_session)
    assert review_session.status == lifecycle.SessionStatus.ready.value

    # Second call — schedule already cleared, no new audit events
    activations_before = len(_audit_rows(db, review_session, "session.activated"))
    scheduled_events.observe_scheduled_events(db, review_session, now=later)
    activations_after = len(_audit_rows(db, review_session, "session.activated"))
    assert activations_after == activations_before


# --------------------------------------------------------------------------- #
# Retry path                                                                  #
# --------------------------------------------------------------------------- #


@pytest.fixture
def patched_activate_raises_transient(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[int]]:
    """Patch lifecycle.activate_session to raise a non-LifecycleError on
    each call. Returns a counter list that the patch increments."""
    calls = [0]

    def _raise(*args: object, **kwargs: object) -> None:
        calls[0] += 1
        raise RuntimeError(f"simulated transient failure #{calls[0]}")

    monkeypatch.setattr(
        "app.services.scheduled_events.lifecycle.activate_session", _raise
    )
    yield calls


def test_observer_emits_retry_on_transient_failure(
    db: Session, patched_activate_raises_transient: list[int]
) -> None:
    """When activate_session raises a non-precondition error, the
    trigger writes a retry audit and *keeps* the schedule set."""
    review_session = _make_validated_session(db, "retry-first")
    review_session.scheduled_activate_at = datetime(
        2099, 1, 1, 9, 0, tzinfo=timezone.utc
    )
    db.flush()
    db.commit()

    later = datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc)
    scheduled_events.observe_scheduled_events(db, review_session, now=later)
    db.refresh(review_session)

    assert review_session.status == lifecycle.SessionStatus.validated.value
    assert review_session.scheduled_activate_at is not None  # NOT cleared
    retries = _audit_rows(db, review_session, "session.scheduled_activation_retry")
    assert len(retries) == 1
    assert retries[0].detail["context"]["attempt"] == 1


def test_observer_fails_persistent_after_three_retries(
    db: Session, patched_activate_raises_transient: list[int]
) -> None:
    """After 3 retry audits, the 4th attempt emits failed_persistent
    and clears the schedule."""
    review_session = _make_validated_session(db, "retry-exhaust")
    review_session.scheduled_activate_at = datetime(
        2099, 1, 1, 9, 0, tzinfo=timezone.utc
    )
    db.flush()
    db.commit()

    later = datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc)
    # 4 invocations → 3 retries + 1 failed_persistent
    for _ in range(4):
        scheduled_events.observe_scheduled_events(db, review_session, now=later)
    db.refresh(review_session)

    retries = _audit_rows(db, review_session, "session.scheduled_activation_retry")
    failed = _audit_rows(
        db, review_session, "session.scheduled_activation_failed_persistent"
    )
    assert len(retries) == 3
    assert len(failed) == 1
    assert failed[0].detail["context"]["attempts"] == 4
    assert review_session.scheduled_activate_at is None


def test_retry_counter_scoped_to_current_scheduled_at(
    db: Session, patched_activate_raises_transient: list[int]
) -> None:
    """If the operator changes scheduled_activate_at after a failure,
    the retry counter resets — the new schedule starts fresh."""
    review_session = _make_validated_session(db, "retry-reschedule")
    first = datetime(2099, 1, 1, 9, 0, tzinfo=timezone.utc)
    review_session.scheduled_activate_at = first
    db.flush()
    db.commit()

    later = datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc)
    # Emit two retries against the first schedule
    scheduled_events.observe_scheduled_events(db, review_session, now=later)
    scheduled_events.observe_scheduled_events(db, review_session, now=later)
    assert len(_audit_rows(db, review_session, "session.scheduled_activation_retry")) == 2

    # Operator reschedules
    second = datetime(2099, 2, 1, 9, 0, tzinfo=timezone.utc)
    review_session.scheduled_activate_at = second
    db.flush()
    db.commit()

    # Fire against the new schedule — should be attempt=1, not attempt=3
    later2 = datetime(2099, 2, 1, 10, 0, tzinfo=timezone.utc)
    scheduled_events.observe_scheduled_events(db, review_session, now=later2)
    retries = _audit_rows(db, review_session, "session.scheduled_activation_retry")
    assert len(retries) == 3
    # Last retry should be attempt=1 against the new scheduled_at
    last = retries[-1]
    assert last.detail["context"]["attempt"] == 1
    assert second.isoformat() in last.detail["context"]["scheduled_at"]


# --------------------------------------------------------------------------- #
# context.trigger provenance — both paths                                     #
# --------------------------------------------------------------------------- #


def test_operator_activation_still_records_trigger_operator(db: Session) -> None:
    """The manual-activate path defaults trigger='operator' — guards
    against regression of the default-arg behaviour."""
    review_session = _make_validated_session(db, "trigger-op")
    op = db.execute(
        select(User).where(User.email == "op-trigger-op@example.edu")
    ).scalar_one()

    issues = []  # empty issues = clean report
    report = lifecycle.build_readiness_report(issues)
    lifecycle.activate_session(
        db,
        review_session=review_session,
        user=op,
        report=report,
        acknowledge_warnings=False,
    )
    db.refresh(review_session)
    assert review_session.status == lifecycle.SessionStatus.ready.value
    activations = _audit_rows(db, review_session, "session.activated")
    assert len(activations) == 1
    assert activations[0].detail["context"]["trigger"] == "operator"


def test_scheduled_activation_clears_schedule_via_activate_session(
    db: Session,
) -> None:
    """Direct call to activate_session with trigger='scheduled' (not
    via the observer) also clears scheduled_activate_at — confirms
    the side effect is on the service, not the trigger wrapper."""
    review_session = _make_validated_session(db, "manual-clear")
    review_session.scheduled_activate_at = datetime(
        2099, 1, 1, 9, 0, tzinfo=timezone.utc
    )
    db.flush()
    db.commit()

    issues = []
    report = lifecycle.build_readiness_report(issues)
    lifecycle.activate_session(
        db,
        review_session=review_session,
        user=None,
        report=report,
        acknowledge_warnings=True,
        trigger="scheduled",
    )
    db.refresh(review_session)
    assert review_session.scheduled_activate_at is None


# --------------------------------------------------------------------------- #
# Manual activate clears the schedule too                                     #
# --------------------------------------------------------------------------- #


def test_manual_activate_clears_pending_scheduled_activate_at(
    db: Session,
) -> None:
    """Operator clicks Activate at 8:30 for a 9:00 scheduled session.
    activate_session clears scheduled_activate_at as a side effect.
    The 9:00 trigger then sees status=ready and no schedule → no-op."""
    review_session = _make_validated_session(db, "manual-pre-empt")
    review_session.scheduled_activate_at = datetime(
        2099, 1, 1, 9, 0, tzinfo=timezone.utc
    )
    db.flush()
    db.commit()

    op = db.execute(
        select(User).where(User.email == "op-manual-pre-empt@example.edu")
    ).scalar_one()

    issues = []
    report = lifecycle.build_readiness_report(issues)
    lifecycle.activate_session(
        db,
        review_session=review_session,
        user=op,
        report=report,
        acknowledge_warnings=False,
    )
    db.refresh(review_session)
    assert review_session.status == lifecycle.SessionStatus.ready.value
    assert review_session.scheduled_activate_at is None

    # Now the would-be-scheduled fire time arrives — observer should no-op
    later = datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc)
    activations_before = len(_audit_rows(db, review_session, "session.activated"))
    scheduled_events.observe_scheduled_events(db, review_session, now=later)
    activations_after = len(_audit_rows(db, review_session, "session.activated"))
    assert activations_after == activations_before
