"""Trigger: scheduled ``validated → ready`` activation (Part 1).

Includes the observer-side trigger + its audit-emit helpers + the
retry counter + the editor-side parser (``parse_and_validate_scheduled_activate_at``).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditEvent, ReviewSession
from app.services import audit, date_formatting
from app.services import session_lifecycle as lifecycle
from app.services import validation

from ._shared import ScheduledActivateError, _ensure_aware_utc, lock_session


_ACTIVATION_MAX_RETRIES = 3


def _observe_scheduled_activation(
    db: Session,
    session: ReviewSession,
    *,
    now: datetime,
    correlation_id: str | None,
) -> None:
    """Fire the scheduled ``validated → ready`` transition if due
    and the precondition is met.

    Contract (per ``spec/lifecycle.md`` §8.2.3 + §8.3 + the Part 1
    plan section):

    - **Not due yet** — ``scheduled_activate_at > now`` → no-op.
    - **Anchor null** — ``scheduled_activate_at is None`` → no-op
      (cross-cutting anchor-null rule).
    - **Precondition miss** — session is not ``validated``:
      one-shot skip. Audit ``session.scheduled_activation_skipped``
      with ``reason``; clear ``scheduled_activate_at``.
    - **Transient transition failure** (e.g. ``activate_session``
      raises a non-precondition error): audit
      ``session.scheduled_activation_retry``; **do not** clear the
      schedule. Retries paced by subsequent operator visits.
    - **3 retries exhausted**: audit
      ``session.scheduled_activation_failed_persistent``; clear
      the schedule.
    - **Success**: ``activate_session`` clears the schedule as a
      side effect; emits ``session.activated`` with
      ``context.trigger="scheduled"``.

    The concurrency model is :func:`lock_session` +
    idempotency check (``locked.scheduled_activate_at is None``)
    in the same transaction as any mutation; a second racer sees
    the first racer's commit and bails.
    """
    if session.scheduled_activate_at is None:
        return
    if _ensure_aware_utc(session.scheduled_activate_at) > now:
        return

    locked = lock_session(db, session)
    if locked.scheduled_activate_at is None:
        return

    scheduled_at_iso = _ensure_aware_utc(
        locked.scheduled_activate_at
    ).isoformat()

    if not lifecycle.is_validated(locked):
        _emit_activation_skipped(
            db,
            locked,
            reason="not_validated",
            scheduled_at_iso=scheduled_at_iso,
            status_at_fire=locked.status,
            correlation_id=correlation_id,
        )
        return

    try:
        issues = validation.validate_session_setup(db, locked)
        report = lifecycle.build_readiness_report(issues)
        lifecycle.activate_session(
            db,
            review_session=locked,
            user=None,
            report=report,
            acknowledge_warnings=True,
            correlation_id=correlation_id,
            trigger="scheduled",
        )
    except lifecycle.LifecycleError as exc:
        # Precondition failures map to one-shot skips; the operator
        # needs to intervene (re-validate / re-schedule) — retrying
        # the same broken setup won't help.
        if exc.code in {"not_validated", "has_errors", "needs_acknowledge"}:
            _emit_activation_skipped(
                db,
                locked,
                reason=exc.code,
                scheduled_at_iso=scheduled_at_iso,
                status_at_fire=locked.status,
                correlation_id=correlation_id,
            )
            return
        # Any other LifecycleError code is unexpected — treat as transient.
        db.rollback()
        _emit_activation_retry_or_failed(
            db,
            locked,
            error=exc,
            scheduled_at_iso=scheduled_at_iso,
            correlation_id=correlation_id,
        )
    except Exception as exc:  # noqa: BLE001 — observer must keep page rendering
        db.rollback()
        _emit_activation_retry_or_failed(
            db,
            locked,
            error=exc,
            scheduled_at_iso=scheduled_at_iso,
            correlation_id=correlation_id,
        )


def _emit_activation_skipped(
    db: Session,
    session: ReviewSession,
    *,
    reason: str,
    scheduled_at_iso: str,
    status_at_fire: str,
    correlation_id: str | None,
) -> None:
    """One-shot skip: write the audit row, clear the schedule, commit."""
    audit.write_event(
        db,
        event_type="session.scheduled_activation_skipped",
        summary=(
            f"Scheduled activation for {session.code} skipped "
            f"({reason})"
        ),
        actor_user_id=None,
        session=session,
        reason=reason,
        context={
            "scheduled_at": scheduled_at_iso,
            "status_at_fire": status_at_fire,
        },
        correlation_id=correlation_id,
    )
    session.scheduled_activate_at = None
    db.flush()
    db.commit()


def _emit_activation_retry_or_failed(
    db: Session,
    session: ReviewSession,
    *,
    error: Exception,
    scheduled_at_iso: str,
    correlation_id: str | None,
) -> None:
    """Transient failure path: retry up to N times, then fail-persistent.

    Retry count is derived from the audit log
    (``session.scheduled_activation_retry`` events scoped to this
    scheduled-fire moment via ``context.scheduled_at``), so no new
    attempt-counter column is needed.
    """
    retry_count = _count_recent_retries(db, session, scheduled_at_iso)
    error_text = repr(error)[:200]

    if retry_count >= _ACTIVATION_MAX_RETRIES:
        audit.write_event(
            db,
            event_type="session.scheduled_activation_failed_persistent",
            summary=(
                f"Scheduled activation for {session.code} gave up "
                f"after {_ACTIVATION_MAX_RETRIES} retries"
            ),
            actor_user_id=None,
            session=session,
            reason=error_text,
            context={
                "scheduled_at": scheduled_at_iso,
                "attempts": retry_count + 1,
            },
            correlation_id=correlation_id,
        )
        session.scheduled_activate_at = None
        db.flush()
        db.commit()
        return

    audit.write_event(
        db,
        event_type="session.scheduled_activation_retry",
        summary=(
            f"Scheduled activation for {session.code} will retry "
            f"(attempt {retry_count + 1})"
        ),
        actor_user_id=None,
        session=session,
        reason=error_text,
        context={
            "scheduled_at": scheduled_at_iso,
            "attempt": retry_count + 1,
        },
        correlation_id=correlation_id,
    )
    db.commit()


def _count_recent_retries(
    db: Session,
    session: ReviewSession,
    scheduled_at_iso: str,
) -> int:
    """Count ``session.scheduled_activation_retry`` events for the
    current scheduled-fire moment.

    Scoped to ``context.scheduled_at == scheduled_at_iso`` so that
    a *new* schedule (operator changed scheduled_activate_at after
    a prior failure) starts a fresh attempt count.
    """
    rows = db.execute(
        select(AuditEvent).where(
            AuditEvent.session_id == session.id,
            AuditEvent.event_type == "session.scheduled_activation_retry",
        )
    ).scalars()
    count = 0
    for row in rows:
        detail = row.detail or {}
        if not isinstance(detail, dict):
            continue
        context = detail.get("context") or {}
        if isinstance(context, dict) and context.get("scheduled_at") == scheduled_at_iso:
            count += 1
    return count


def parse_and_validate_scheduled_activate_at(
    raw: str | None,
    *,
    timezone_name: str,
    now: datetime | None = None,
    min_lead_hours: int | None = None,
) -> datetime | None:
    """Parse a ``datetime-local`` form value into a UTC-aware datetime
    and enforce the operational lead-time floor (Part 1 minimum
    lead time, defaulted to ``settings.scheduled_operational_lead_hours``).

    Returns ``None`` when ``raw`` is empty (operator cleared the
    field). Raises :class:`ScheduledActivateError` on a malformed
    string or when the resolved fire moment is closer than the
    floor allows.

    The editor is "always editable" per ``spec/lifecycle.md`` §8.2.1 —
    the operator can set Start whenever, including at session-create
    time before any validation. This helper enforces only the
    minimum-lead-time floor, not the precondition (which is checked
    at fire time by the observer).
    """
    if not raw:
        return None
    try:
        parsed = date_formatting.parse_local_datetime(raw, timezone_name)
    except ValueError as exc:
        raise ScheduledActivateError(
            "Start must be a valid datetime"
        ) from exc
    # date_formatting.parse_local_datetime returns naive-UTC; re-attach
    # the tzinfo for arithmetic against ``now`` (which is aware).
    parsed_aware = _ensure_aware_utc(parsed)

    hours = (
        min_lead_hours
        if min_lead_hours is not None
        else settings.scheduled_operational_lead_hours
    )
    current = now or datetime.now(timezone.utc)
    if parsed_aware - current < timedelta(hours=hours):
        raise ScheduledActivateError(
            f"Scheduled activation must be at least {hours} hour(s) "
            f"in the future"
        )
    return parsed_aware
