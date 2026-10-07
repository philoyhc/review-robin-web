"""Trigger: auto-send reminders (Part 3).

Includes the observer-side trigger + the per-anchor dedup helper +
the reminder-dispatch wrapper + the editor-side parser
(``parse_and_validate_reminder_offsets``).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from collections.abc import Sequence
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import EmailOutbox, ReviewSession
from app.services import audit
from app.services import invitations as invitations_service
from app.services import session_lifecycle as lifecycle

from ._duration import parse_iso_duration
from ._fired import fired_offsets
from ._shared import (
    ScheduledActivateError,
    _OFFSET_MAX_MAGNITUDE,
    _ensure_aware_utc,
    lock_session,
)


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

    Dedup is keyed on ``(session_id, offset_index, context.anchor_at)``,
    the anchor matched to ``deadline`` as an instant
    (``_fired.fired_offsets``). If the operator changes ``deadline``,
    the consumed set resets —
    every entry becomes eligible to fire again against the new anchor.
    """
    # The same record the save-time check reads, matched as an instant
    # (findings Bc1), so the two can never disagree on a position.
    return set(
        fired_offsets(db, session, "reminder", datetime.fromisoformat(anchor_iso))
    )


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
    ``accepting_responses`` flag is intentionally not consulted: it
    is session-wide, and the only thing that clears it on a ``ready``
    session is the deadline, which this window already excludes.

    Concurrency: each entry is decided and recorded in one
    transaction under ``lock_session``, which re-reads the session row
    (findings Bc3). A second racer re-reads the record after the first
    commits and skips the entry; a schedule save waits for the entry to
    be recorded, and an entry decided after a save sees the saved lists.
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

    # One entry per transaction, decided under the session lock and
    # re-read each time (findings Bc3), as the invite pass does. Fire
    # in chronological order so the audit log reads top-to-bottom.
    handled: set[int] = set()
    while True:
        locked = lock_session(db, session)
        if locked.deadline is None or not locked.reminder_offsets:
            db.commit()
            return
        anchor_iso = _ensure_aware_utc(locked.deadline).isoformat()
        consumed = _consumed_reminder_offset_indices(db, locked, anchor_iso)
        pending = sorted(
            (fire_at, idx, raw)
            for idx, raw, fire_at in _resolve_reminder_fires(locked)
            if fire_at is not None
            and fire_at <= now
            and idx not in consumed
            and idx not in handled
        )
        if not pending:
            db.commit()
            return
        fire_at, offset_index, offset_str = pending[0]
        handled.add(offset_index)
        _fire_reminder_entry(
            db,
            locked,
            offset_index=offset_index,
            offset_str=offset_str,
            anchor_iso=anchor_iso,
            scheduled_iso=fire_at.isoformat(),
            now=now,
            correlation_id=correlation_id,
            build_invite_url=build_invite_url,
        )
        db.commit()


def _fire_reminder_entry(
    db: Session,
    locked: ReviewSession,
    *,
    offset_index: int,
    offset_str: str,
    anchor_iso: str,
    scheduled_iso: str,
    now: datetime,
    correlation_id: str | None,
    build_invite_url: Callable[[str], str],
) -> None:
    """Skip or send one due entry and record it, without committing:
    the caller commits the entry as one transaction."""
    context = {
        "anchor_at": anchor_iso,
        "offset_index": offset_index,
        "offset": offset_str,
        "scheduled_at": scheduled_iso,
    }
    if not lifecycle.is_ready(locked):
        skip_reason: str | None = "not_ready"
    elif not invitations_service.has_invitations(db, locked.id):
        skip_reason = "no_invitations"
    elif now >= _ensure_aware_utc(locked.deadline):
        skip_reason = "outside_response_window"
    else:
        skip_reason = None
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
            context=context,
            correlation_id=correlation_id,
        )
        return

    sent = _dispatch_scheduled_reminders(
        db,
        locked,
        offset_index=offset_index,
        build_invite_url=build_invite_url,
        correlation_id=correlation_id,
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
        context={**context, "actual_fired_at": now.isoformat()},
        correlation_id=correlation_id,
    )


def _dispatch_scheduled_reminders(
    db: Session,
    session: ReviewSession,
    *,
    offset_index: int,
    build_invite_url: Callable[[str], str],
    correlation_id: str | None = None,
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
        # The dedupe stamp rides on the outbox row (findings B31), which
        # the caller commits with the entry's audit row as one
        # transaction (findings Bc3): a failure part-way rolls the whole
        # entry back, and the next pass sends it afresh.
        invitations_service.send_reminder(
            db,
            invitation=row.invitation,
            review_session=session,
            reviewer=row.reviewer,
            user=None,
            build_invite_url=build_invite_url,
            correlation_id=correlation_id,
            outbox_correlation_id=cid,
            commit=False,
        )
        sent += 1
    return sent


def parse_and_validate_reminder_offsets(
    raw: str | None,
    *,
    deadline: datetime | None,
    now: datetime | None = None,
    operational_lead_hours: int | None = None,
    notice_min_hours: int | None = None,
    aged_exempt: Sequence[frozenset[str]] = (),
) -> list[str] | None:
    """Parse a comma-separated reminder-offsets string into a clean
    list and enforce the per-entry save-time rules (Segment 18G PR 3B).

    Same shape as :func:`parse_and_validate_invite_offsets` but
    anchored on ``sessions.deadline`` (End) rather than
    ``scheduled_activate_at``. Each entry must be a negative ISO 8601
    duration — reminders fire *before* the deadline.

    Returns ``None`` when ``raw`` is empty. When ``raw`` is set,
    splits on commas, strips whitespace, drops empty fragments, and
    for each remaining entry:

    1. Parses as an ISO 8601 duration (per §8.2.4).
    2. When ``deadline`` is set:
       - resolved fire moment (``deadline + offset``)
         ≥ ``now + operational_lead_hours``
       - ``|offset|`` ≥ ``notice_min_hours``
       - ``offset < 0`` (the entry fires before End).
    3. When ``deadline`` is unset: parse-only validation per the
       §8.2.2 anchor-null rule; the entry is inert at fire time.

    ``aged_exempt`` is, per position, the entries that may stay there
    past the lead-time floor (``offsets_lead_exempt``): the stored one
    while the anchor is unedited, which aged past the floor after saving
    and "stays put" (findings B4), and the one already sent there on
    the anchor (findings Bc1; ``spec/lifecycle.md`` §8.2.6, §8.3). Only
    the lead-time floor is waived; every other rule still applies.
    Matching is by position, not value, because the observer tracks
    fired offsets by index: a duplicate, or a stored entry moved to
    another position, meets the floor like any new one.

    Raises :class:`ScheduledActivateError` with a per-entry message on
    the first violation. The route layer converts to HTTP 422.
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
    for index, entry in enumerate(entries):
        try:
            delta = parse_iso_duration(entry)
        except ValueError as exc:
            raise ScheduledActivateError(
                f"Auto-send reminder {entry!r} isn't a valid ISO 8601 duration."
            ) from exc

        if abs(delta) > _OFFSET_MAX_MAGNITUDE:
            raise ScheduledActivateError(
                f"Auto-send reminder {entry} exceeds the 10-day "
                f"maximum offset magnitude; choose a smaller "
                f"duration."
            )

        if deadline is not None:
            anchor = _ensure_aware_utc(deadline)
            fire_at = anchor + delta
            exempt = (
                index < len(aged_exempt) and entry in aged_exempt[index]
            )
            if not exempt and fire_at - current < timedelta(hours=op_hours):
                raise ScheduledActivateError(
                    f"Auto-send reminder {entry} resolves to before now + "
                    f"{op_hours} hour(s); leave more lead time."
                )
            if abs(delta) < timedelta(hours=notice_hours):
                raise ScheduledActivateError(
                    f"Auto-send reminder {entry} gives less than "
                    f"{notice_hours} hour(s) between reminder and End; "
                    f"minimum reviewer notice is {notice_hours} hour(s)."
                )
            if delta >= timedelta(0):
                raise ScheduledActivateError(
                    f"Auto-send reminder {entry} fires at or after End; "
                    f"use a negative duration (e.g. -P1D)."
                )
        cleaned.append(entry)
    return cleaned
