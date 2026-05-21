"""Lazy observer for scheduled session-lifecycle events (Segment 18G).

Per ``spec/lifecycle.md`` §8.2 + §8.3: scheduled events fire on
operator GETs to session-related pages. Each trigger checks its
precondition (§8.2.3), uses ``SELECT … FOR UPDATE`` on the
session row, and is idempotent via the column clear at the end
of a successful fire.

**PR 1A — scaffolding only.** This module ships the lazy-observer
skeleton without any wired triggers. Subsequent PRs register
per-event triggers inside :func:`observe_scheduled_events`:

- PR 1B — scheduled activation
- PR 2A — auto-send invitations
- Parts 3 / 4 / 5 — reminders, auto-archive, scheduled purge

The ``(db, session, now, correlation_id)`` signature is the
contract every trigger consumes.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditEvent, ReviewSession
from app.services import audit, date_formatting
from app.services import session_lifecycle as lifecycle
from app.services import validation


# --------------------------------------------------------------------------- #
# ISO 8601 duration parsing                                                   #
# --------------------------------------------------------------------------- #


_ISO_DURATION_RE = re.compile(
    r"^(?P<sign>-)?P"
    r"(?:(?P<years>\d+)Y)?"
    r"(?:(?P<months>\d+)M)?"
    r"(?:(?P<days>\d+)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+)S)?"
    r")?$"
)


def parse_iso_duration(text: str) -> timedelta:
    """Parse an ISO 8601 duration string into a :class:`datetime.timedelta`.

    Accepts the standard designators only
    (``P[n]Y[n]M[n]DT[n]H[n]M[n]S``), with an optional leading minus
    sign for negative durations. Fractional values and weeks (``P1W``)
    are rejected per ``spec/lifecycle.md`` §8.2.4.

    Years and months are approximated: 1Y = 365d, 1M = 30d. Scheduled
    offsets in practice use only days / hours / minutes / seconds, so
    the approximation rarely matters; documented here so callers can
    avoid feeding years / months into a precision-sensitive context.
    """
    match = _ISO_DURATION_RE.fullmatch(text.strip())
    if match is None:
        raise ValueError(f"not an ISO 8601 duration: {text!r}")
    parts = match.groupdict()
    body_keys = ("years", "months", "days", "hours", "minutes", "seconds")
    if all(parts[k] is None for k in body_keys):
        raise ValueError(f"empty ISO 8601 duration: {text!r}")
    years = int(parts["years"] or 0)
    months = int(parts["months"] or 0)
    days = int(parts["days"] or 0)
    hours = int(parts["hours"] or 0)
    minutes = int(parts["minutes"] or 0)
    seconds = int(parts["seconds"] or 0)
    total = timedelta(
        days=years * 365 + months * 30 + days,
        hours=hours,
        minutes=minutes,
        seconds=seconds,
    )
    if parts["sign"] == "-":
        total = -total
    return total


# --------------------------------------------------------------------------- #
# Offset resolution                                                           #
# --------------------------------------------------------------------------- #


def _ensure_aware_utc(value: datetime) -> datetime:
    """SQLite stores naive timestamps even with ``DateTime(timezone=True)``;
    treat them as UTC for comparison purposes."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def resolve_offset(
    session: ReviewSession,
    anchor_field: str,
    offset_field: str,
) -> datetime | None:
    """Resolve an anchor + offset pair into an absolute fire datetime.

    Returns ``None`` when either the anchor column or the offset
    column is null — the §8.2.2 anchor-null inertness rule. Also
    returns ``None`` when the offset string fails to parse, so the
    caller doesn't need to wrap each call in a try/except; the
    trigger should audit the malformed value via a separate path.

    Otherwise returns ``anchor + parse_iso_duration(offset)`` as a
    timezone-aware datetime.
    """
    anchor = getattr(session, anchor_field, None)
    offset = getattr(session, offset_field, None)
    if anchor is None or offset is None:
        return None
    try:
        delta = parse_iso_duration(offset)
    except ValueError:
        return None
    return _ensure_aware_utc(anchor) + delta


# --------------------------------------------------------------------------- #
# Session lock + observer entry point                                         #
# --------------------------------------------------------------------------- #


def lock_session(db: Session, session: ReviewSession) -> ReviewSession:
    """``SELECT … FOR UPDATE`` the session row + return the (refreshed)
    row.

    Used by triggers to prevent two concurrent operator GETs from
    racing the same fire. The Postgres path takes a row-level lock;
    SQLite silently no-ops the ``FOR UPDATE`` (single-writer DB),
    which is acceptable for the dev loop.

    The caller is expected to follow with an **idempotency check**
    on the relevant schedule column inside the same transaction —
    e.g. ``if locked.scheduled_activate_at is None: return`` — so
    that a second racer sees the first racer's commit and bails.
    """
    return db.execute(
        select(ReviewSession)
        .where(ReviewSession.id == session.id)
        .with_for_update()
    ).scalar_one()


def observe_scheduled_events(
    db: Session,
    session: ReviewSession,
    *,
    now: datetime | None = None,
    correlation_id: str | None = None,
) -> None:
    """Lazy observer entry point — called from session-related GETs
    (Session Home, Operations pages, the Sessions lobby).

    Fires any scheduled-event triggers whose fire-time has passed
    and whose preconditions are met. Idempotent and concurrency-safe
    via :func:`lock_session` + each trigger's idempotency check.

    Triggers wired so far:

    - PR 1B — :func:`_observe_scheduled_activation`

    The ``(db, session, now, correlation_id)`` contract is what each
    trigger consumes; ``now`` is resolved once up-front so all
    triggers in this pass see the same clock.
    """
    current = now or datetime.now(timezone.utc)
    _observe_scheduled_activation(
        db, session, now=current, correlation_id=correlation_id
    )


# --------------------------------------------------------------------------- #
# Trigger: scheduled activation (Part 1)                                      #
# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #
# Editor-side parse + validate (PR 1C)                                        #
# --------------------------------------------------------------------------- #


class ScheduledActivateError(ValueError):
    """Raised when a Start datetime fails parse / validation at save.

    The route layer converts to ``HTTPException(422, detail=str(exc))``.
    """


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
