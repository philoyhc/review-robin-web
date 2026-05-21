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

from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import (
    AuditEvent,
    EmailOutbox,
    Invitation,
    ReviewSession,
    Reviewer,
)
from app.services import audit, date_formatting
from app.services import invitations as invitations_service
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
    build_invite_url: Callable[[str], str] | None = None,
) -> None:
    """Lazy observer entry point — called from session-related GETs
    (Session Home, Operations pages, the Sessions lobby).

    Fires any scheduled-event triggers whose fire-time has passed
    and whose preconditions are met. Idempotent and concurrency-safe
    via :func:`lock_session` + each trigger's idempotency check.

    Triggers wired so far:

    - PR 1B — :func:`_observe_scheduled_activation`
    - PR 2A — :func:`_observe_scheduled_invites`
    - PR 3A — :func:`_observe_scheduled_reminders`

    ``build_invite_url`` is the URL builder consumed by the
    invite-dispatch path (``send_invitation`` in
    ``app.services.invitations``). The caller — typically the
    Session Home GET handler — passes
    ``lambda token: str(request.url_for("reviewer_invite", token=token))``.
    When omitted the invite trigger no-ops (a stand-alone
    background-worker dispatch path will plumb a deployment-base-URL
    closure here).

    The ``(db, session, now, correlation_id, …)`` contract is what
    each trigger consumes; ``now`` is resolved once up-front so all
    triggers in this pass see the same clock — and the catch-up
    ordering (past-due invites fire before activation in the same
    pass) is the natural order below.
    """
    current = now or datetime.now(timezone.utc)
    _observe_scheduled_invites(
        db,
        session,
        now=current,
        correlation_id=correlation_id,
        build_invite_url=build_invite_url,
    )
    _observe_scheduled_activation(
        db, session, now=current, correlation_id=correlation_id
    )
    _observe_scheduled_reminders(
        db,
        session,
        now=current,
        correlation_id=correlation_id,
        build_invite_url=build_invite_url,
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


# --------------------------------------------------------------------------- #
# Trigger: auto-send invitations (Part 2)                                     #
# --------------------------------------------------------------------------- #


def _resolve_invite_fires(
    session: ReviewSession,
) -> list[tuple[int, str, datetime | None]]:
    """Resolve every ``invite_offsets`` entry into a fire datetime
    (or ``None`` when the entry parses but the anchor is unset, or
    when the entry itself is unparseable).

    Returns a list of ``(offset_index, offset_str, fire_at)``
    tuples, preserving the original list order. The caller filters
    by ``fire_at <= now`` to find due entries.
    """
    offsets = session.invite_offsets or []
    if not isinstance(offsets, list):
        return []
    anchor = session.scheduled_activate_at
    fires: list[tuple[int, str, datetime | None]] = []
    for index, raw in enumerate(offsets):
        if not isinstance(raw, str):
            fires.append((index, repr(raw), None))
            continue
        if anchor is None:
            fires.append((index, raw, None))
            continue
        try:
            delta = parse_iso_duration(raw)
        except ValueError:
            fires.append((index, raw, None))
            continue
        fires.append((index, raw, _ensure_aware_utc(anchor) + delta))
    return fires


def _consumed_invite_offset_indices(
    db: Session,
    session: ReviewSession,
    anchor_iso: str,
) -> set[int]:
    """Return the set of ``invite_offsets`` indices already fired or
    skipped for the current anchor moment.

    Dedup is keyed on ``(session_id, offset_index, context.scheduled_at
    == anchor.scheduled_activate_at)``. If the operator reschedules
    Start (new anchor ISO), the consumed set resets — every entry
    becomes eligible to fire again against the new anchor.
    """
    consumed: set[int] = set()
    rows = db.execute(
        select(AuditEvent).where(
            AuditEvent.session_id == session.id,
            AuditEvent.event_type.in_(
                (
                    "session.scheduled_invites_fired",
                    "session.scheduled_invites_skipped",
                )
            ),
        )
    ).scalars()
    for row in rows:
        detail = row.detail or {}
        if not isinstance(detail, dict):
            continue
        ctx = detail.get("context") or {}
        if not isinstance(ctx, dict):
            continue
        if ctx.get("anchor_at") != anchor_iso:
            continue
        idx = ctx.get("offset_index")
        if isinstance(idx, int):
            consumed.add(idx)
    return consumed


def _observe_scheduled_invites(
    db: Session,
    session: ReviewSession,
    *,
    now: datetime,
    correlation_id: str | None,
    build_invite_url: Callable[[str], str] | None,
) -> None:
    """Fire any past-due ``invite_offsets`` entries.

    Contract (per ``spec/lifecycle.md`` §8.2 + §8.3 + the Part 2
    plan section):

    - **Anchor unset / no offsets** → no-op (anchor-null inertness).
    - **No URL builder available** → no-op (cannot dispatch).
    - For each entry whose resolved fire moment ≤ ``now`` and that
      hasn't been fired/skipped yet at this anchor:
      - **Precondition miss** (no ``Invitation`` rows on the session):
        one-shot skip per entry, audit
        ``session.scheduled_invites_skipped`` with
        ``reason="invitations_not_created"``.
      - **Precondition met**: dispatch pending invitations via
        ``invitations_service.send_invitation`` with
        ``trigger="scheduled"``. Audit
        ``session.scheduled_invites_fired`` carrying
        ``counts.sent`` + ``context.scheduled_at`` /
        ``context.actual_fired_at`` (so observer-lag late-fires are
        observable).

    Per-entry dedup is keyed on
    ``(session_id, offset_index, anchor=scheduled_activate_at.isoformat)``.
    Operator changing ``scheduled_activate_at`` resets the dedup set
    — every entry gets a fresh chance against the new anchor.

    Concurrency is the same SELECT … FOR UPDATE pattern as Part 1:
    the session row is locked once before iterating; each entry's
    audit-driven consumption check inside that transaction prevents
    a second racer from re-firing the same entry.
    """
    if not session.invite_offsets:
        return
    if session.scheduled_activate_at is None:
        return
    if build_invite_url is None:
        return

    fires = _resolve_invite_fires(session)
    due = [
        (idx, raw, fire_at)
        for idx, raw, fire_at in fires
        if fire_at is not None and fire_at <= now
    ]
    if not due:
        return

    locked = lock_session(db, session)
    if locked.scheduled_activate_at is None or not locked.invite_offsets:
        return

    anchor_iso = _ensure_aware_utc(locked.scheduled_activate_at).isoformat()
    consumed = _consumed_invite_offset_indices(db, locked, anchor_iso)

    has_invitations = invitations_service.has_invitations(db, locked.id)

    # Fire in chronological order so the audit log reads top-to-bottom.
    due_sorted = sorted(due, key=lambda row: row[2])  # by fire_at
    for offset_index, offset_str, fire_at in due_sorted:
        if offset_index in consumed:
            continue
        scheduled_iso = fire_at.isoformat()
        if not has_invitations:
            audit.write_event(
                db,
                event_type="session.scheduled_invites_skipped",
                summary=(
                    f"Scheduled invites for {locked.code} skipped "
                    f"({offset_str}): invitations_not_created"
                ),
                actor_user_id=None,
                session=locked,
                reason="invitations_not_created",
                context={
                    "anchor_at": anchor_iso,
                    "offset_index": offset_index,
                    "offset": offset_str,
                    "scheduled_at": scheduled_iso,
                },
                correlation_id=correlation_id,
            )
            consumed.add(offset_index)
            db.commit()
            continue

        sent = _dispatch_pending_invitations(
            db,
            locked,
            build_invite_url=build_invite_url,
            correlation_id=correlation_id,
        )

        audit.write_event(
            db,
            event_type="session.scheduled_invites_fired",
            summary=(
                f"Scheduled invites for {locked.code} fired "
                f"({offset_str}); dispatched {sent}"
            ),
            actor_user_id=None,
            session=locked,
            payload=audit.counts(sent=sent),
            context={
                "anchor_at": anchor_iso,
                "offset_index": offset_index,
                "offset": offset_str,
                "scheduled_at": scheduled_iso,
                "actual_fired_at": now.isoformat(),
            },
            correlation_id=correlation_id,
        )
        consumed.add(offset_index)
        db.commit()


def _dispatch_pending_invitations(
    db: Session,
    session: ReviewSession,
    *,
    build_invite_url: Callable[[str], str],
    correlation_id: str | None,
) -> int:
    """Send every pending invitation on the session via the existing
    operator path, marked as a scheduled trigger.

    Returns the count actually dispatched (zero when all invitations
    have already been sent — the entry is still marked consumed so
    the trigger doesn't keep retrying on each observer pass).
    """
    pending = db.execute(
        select(Invitation, Reviewer)
        .join(Reviewer, Reviewer.id == Invitation.reviewer_id)
        .where(Invitation.session_id == session.id)
        .where(Invitation.status == "pending")
    ).all()

    sent = 0
    for invitation, reviewer in pending:
        invitations_service.send_invitation(
            db,
            invitation=invitation,
            review_session=session,
            reviewer=reviewer,
            user=None,
            build_invite_url=build_invite_url,
            correlation_id=correlation_id,
            trigger="scheduled",
        )
        sent += 1
    return sent


# --------------------------------------------------------------------------- #
# Trigger: auto-send reminders (Part 3)                                       #
# --------------------------------------------------------------------------- #


def _resolve_reminder_fires(
    session: ReviewSession,
) -> list[tuple[int, str, datetime | None]]:
    """Resolve every ``reminder_offsets`` entry against ``deadline``.

    Same shape as :func:`_resolve_invite_fires` but anchored on
    ``sessions.deadline`` (End) rather than ``scheduled_activate_at``.
    Returns ``(offset_index, offset_str, fire_at)`` tuples in list
    order; ``fire_at`` is ``None`` when the anchor is unset or the
    entry is unparseable.
    """
    offsets = session.reminder_offsets or []
    if not isinstance(offsets, list):
        return []
    anchor = session.deadline
    fires: list[tuple[int, str, datetime | None]] = []
    for index, raw in enumerate(offsets):
        if not isinstance(raw, str):
            fires.append((index, repr(raw), None))
            continue
        if anchor is None:
            fires.append((index, raw, None))
            continue
        try:
            delta = parse_iso_duration(raw)
        except ValueError:
            fires.append((index, raw, None))
            continue
        fires.append((index, raw, _ensure_aware_utc(anchor) + delta))
    return fires


def _consumed_reminder_offset_indices(
    db: Session,
    session: ReviewSession,
    anchor_iso: str,
) -> set[int]:
    """Return the set of ``reminder_offsets`` indices already fired or
    skipped for the current anchor moment.

    Dedup is keyed on
    ``(session_id, offset_index, context.anchor_at == deadline.isoformat)``.
    If the operator changes ``deadline``, the consumed set resets —
    every entry becomes eligible to fire again against the new anchor.
    """
    consumed: set[int] = set()
    rows = db.execute(
        select(AuditEvent).where(
            AuditEvent.session_id == session.id,
            AuditEvent.event_type.in_(
                (
                    "session.scheduled_reminders_fired",
                    "session.scheduled_reminders_skipped",
                )
            ),
        )
    ).scalars()
    for row in rows:
        detail = row.detail or {}
        if not isinstance(detail, dict):
            continue
        ctx = detail.get("context") or {}
        if not isinstance(ctx, dict):
            continue
        if ctx.get("anchor_at") != anchor_iso:
            continue
        idx = ctx.get("offset_index")
        if isinstance(idx, int):
            consumed.add(idx)
    return consumed


def _observe_scheduled_reminders(
    db: Session,
    session: ReviewSession,
    *,
    now: datetime,
    correlation_id: str | None,
    build_invite_url: Callable[[str], str] | None,
) -> None:
    """Fire any past-due ``reminder_offsets`` entries.

    Contract (per ``spec/lifecycle.md`` §8.2 + §8.3 + the Part 3
    plan section):

    - **Anchor unset / no offsets** → no-op (anchor-null inertness).
    - **No URL builder available** → no-op (the reminder fallback
      path needs to build invite URLs).
    - For each entry whose resolved fire moment ≤ ``now`` and that
      hasn't been fired/skipped yet at this anchor:
      - **Precondition miss** (session not ``ready`` / no
        ``Invitation`` rows / past deadline): one-shot skip per
        entry, audit ``session.scheduled_reminders_skipped`` with
        ``reason ∈ {"not_ready","no_invitations","outside_response_window"}``.
      - **Precondition met**: dispatch a reminder to every
        incomplete reviewer via the existing operator path
        (:func:`invitations_service.send_reminder`), with per-reviewer
        dedup keyed on
        ``EmailOutbox.correlation_id == "reminder:{sid}:{rid}:{offset_index}"``
        so a partial-failure re-pass doesn't double-send. Audit
        ``session.scheduled_reminders_fired`` carrying
        ``counts.sent`` + ``context.{scheduled_at, actual_fired_at}``.

    Per-entry consume is identical to Part 2: an audit-event check
    on ``(session_id, offset_index, context.anchor_at)``. Operator
    changing ``deadline`` resets the dedup set.

    Accepting-responses window is the **relaxed** definition
    (``status == "ready" ∧ now < deadline``); the per-instrument
    ``accepting_responses`` flag is intentionally not consulted —
    if every instrument has been temporarily closed while the
    session is still ``ready``, sending a reminder is harmless
    (reviewer lands on "responses not currently accepted") and the
    operator can clear ``reminder_offsets`` to suppress.

    Concurrency is the same SELECT … FOR UPDATE pattern as Parts
    1/2: the session row is locked once before iterating; each
    entry's audit-driven consumption check inside that transaction
    prevents a second racer from re-firing the same entry.
    """
    if not session.reminder_offsets:
        return
    if session.deadline is None:
        return
    if build_invite_url is None:
        return

    fires = _resolve_reminder_fires(session)
    due = [
        (idx, raw, fire_at)
        for idx, raw, fire_at in fires
        if fire_at is not None and fire_at <= now
    ]
    if not due:
        return

    locked = lock_session(db, session)
    if locked.deadline is None or not locked.reminder_offsets:
        return

    anchor_iso = _ensure_aware_utc(locked.deadline).isoformat()
    consumed = _consumed_reminder_offset_indices(db, locked, anchor_iso)

    # Precondition resolves once per pass — applies uniformly to every
    # entry firing in this observer call.
    if not lifecycle.is_ready(locked):
        skip_reason: str | None = "not_ready"
    elif not invitations_service.has_invitations(db, locked.id):
        skip_reason = "no_invitations"
    elif now >= _ensure_aware_utc(locked.deadline):
        skip_reason = "outside_response_window"
    else:
        skip_reason = None

    # Fire in chronological order so the audit log reads top-to-bottom.
    due_sorted = sorted(due, key=lambda row: row[2])  # by fire_at
    for offset_index, offset_str, fire_at in due_sorted:
        if offset_index in consumed:
            continue
        scheduled_iso = fire_at.isoformat()
        if skip_reason is not None:
            audit.write_event(
                db,
                event_type="session.scheduled_reminders_skipped",
                summary=(
                    f"Scheduled reminders for {locked.code} skipped "
                    f"({offset_str}): {skip_reason}"
                ),
                actor_user_id=None,
                session=locked,
                reason=skip_reason,
                context={
                    "anchor_at": anchor_iso,
                    "offset_index": offset_index,
                    "offset": offset_str,
                    "scheduled_at": scheduled_iso,
                },
                correlation_id=correlation_id,
            )
            consumed.add(offset_index)
            db.commit()
            continue

        sent = _dispatch_scheduled_reminders(
            db,
            locked,
            offset_index=offset_index,
            build_invite_url=build_invite_url,
        )

        audit.write_event(
            db,
            event_type="session.scheduled_reminders_fired",
            summary=(
                f"Scheduled reminders for {locked.code} fired "
                f"({offset_str}); dispatched {sent}"
            ),
            actor_user_id=None,
            session=locked,
            payload=audit.counts(sent=sent),
            context={
                "anchor_at": anchor_iso,
                "offset_index": offset_index,
                "offset": offset_str,
                "scheduled_at": scheduled_iso,
                "actual_fired_at": now.isoformat(),
            },
            correlation_id=correlation_id,
        )
        consumed.add(offset_index)
        db.commit()


def _dispatch_scheduled_reminders(
    db: Session,
    session: ReviewSession,
    *,
    offset_index: int,
    build_invite_url: Callable[[str], str],
) -> int:
    """Send a reminder to every incomplete reviewer on the session.

    Per-reviewer dedup: skip any reviewer whose
    ``EmailOutbox.correlation_id == "reminder:{sid}:{rid}:{offset_index}"``
    already exists — handles the partial-failure case where an
    earlier observer pass dispatched to some reviewers, failed
    mid-loop without committing the ``_fired`` audit row, and now
    re-runs against the same entry.

    Returns the count actually dispatched (zero is a valid outcome —
    e.g. every incomplete reviewer was already reminded; the
    ``_fired`` event still emits so the entry consumes).
    """
    from app.services import monitoring  # local: avoids circular import

    rows = monitoring.per_reviewer_progress(db, session)
    sent = 0
    for row in rows:
        if not row.is_incomplete or row.invitation is None:
            continue
        cid = f"reminder:{session.id}:{row.reviewer.id}:{offset_index}"
        existing = db.execute(
            select(EmailOutbox.id).where(EmailOutbox.correlation_id == cid)
        ).scalar_one_or_none()
        if existing is not None:
            continue
        result = invitations_service.send_reminder(
            db,
            invitation=row.invitation,
            review_session=session,
            reviewer=row.reviewer,
            user=None,
            build_invite_url=build_invite_url,
            correlation_id=cid,
        )
        # Stamp the new outbox row so the next observer pass dedups
        # this reviewer at this offset.
        outbox = db.get(EmailOutbox, result.outbox_id)
        if outbox is not None:
            outbox.correlation_id = cid
            db.flush()
        sent += 1
    return sent


def parse_and_validate_invite_offsets(
    raw: str | None,
    *,
    scheduled_activate_at: datetime | None,
    now: datetime | None = None,
    operational_lead_hours: int | None = None,
    notice_min_hours: int | None = None,
) -> list[str] | None:
    """Parse a comma-separated invite-offsets string into a clean list
    and enforce the per-entry save-time rules.

    Returns ``None`` when ``raw`` is empty (operator cleared the
    field). When ``raw`` is set, splits on commas, strips whitespace,
    and drops empty fragments. For each entry it then enforces:

    1. Parses as an ISO 8601 duration (per §8.2.4).
    2. When ``scheduled_activate_at`` is set:
       - resolved fire moment (``scheduled_activate_at + offset``)
         ≥ ``now + operational_lead_hours``
       - ``|offset|`` ≥ ``notice_min_hours``
       (per §8.2.1 + the Part 2 plan section's per-offset table)
    3. When ``scheduled_activate_at`` is unset: the entry is inert
       per §8.2.2 anchor-null, so only the parse-validity check
       runs. The editor renders the field with a "Set Start first"
       caption.

    Raises :class:`ScheduledActivateError` with a per-entry error
    message on the first violation. The route layer converts to
    HTTP 422.
    """
    if not raw or not raw.strip():
        return None
    entries = [item.strip() for item in raw.split(",") if item.strip()]
    if not entries:
        return None

    op_hours = (
        operational_lead_hours
        if operational_lead_hours is not None
        else settings.scheduled_operational_lead_hours
    )
    notice_hours = (
        notice_min_hours
        if notice_min_hours is not None
        else settings.reviewer_notice_min_hours
    )
    current = now or datetime.now(timezone.utc)

    cleaned: list[str] = []
    for entry in entries:
        try:
            delta = parse_iso_duration(entry)
        except ValueError as exc:
            raise ScheduledActivateError(
                f"Auto-send invite {entry!r} isn't a valid ISO 8601 duration."
            ) from exc

        if scheduled_activate_at is not None:
            anchor = _ensure_aware_utc(scheduled_activate_at)
            fire_at = anchor + delta
            if fire_at - current < timedelta(hours=op_hours):
                raise ScheduledActivateError(
                    f"Auto-send invite {entry} resolves to before now + "
                    f"{op_hours} hour(s); leave more lead time."
                )
            if abs(delta) < timedelta(hours=notice_hours):
                raise ScheduledActivateError(
                    f"Auto-send invite {entry} gives less than "
                    f"{notice_hours} hour(s) between invite and Start; "
                    f"minimum reviewer notice is {notice_hours} hour(s)."
                )
            if delta >= timedelta(0):
                raise ScheduledActivateError(
                    f"Auto-send invite {entry} fires at or after Start; "
                    f"use a negative duration (e.g. -PT2H)."
                )
        cleaned.append(entry)
    return cleaned
