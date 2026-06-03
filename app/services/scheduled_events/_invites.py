"""Trigger: auto-send invitations (Part 2).

Includes the observer-side trigger + the per-anchor dedup helper +
the invitation-dispatch wrapper + the editor-side parser
(``parse_and_validate_invite_offsets``).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditEvent, Invitation, ReviewSession, Reviewer
from app.services import audit
from app.services import invitations as invitations_service
from app.services import session_lifecycle as lifecycle

from ._duration import parse_iso_duration
from ._shared import (
    ScheduledActivateError,
    _OFFSET_MAX_MAGNITUDE,
    _ensure_aware_utc,
    lock_session,
)


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

    # Preconditions resolve once per pass — both apply uniformly to
    # every entry firing in this observer call. Order matters:
    # `not_prepared` is checked first because invitations are
    # preserved across a revert to draft, so a stale session could
    # otherwise fire invites from `draft` even though manual Send
    # would refuse (the operator route `_require_validated_or_ready`
    # gates the same way).
    is_prepared = lifecycle.is_validated(locked) or lifecycle.is_ready(locked)
    has_invitations = invitations_service.has_invitations(db, locked.id)

    # Fire in chronological order so the audit log reads top-to-bottom.
    due_sorted = sorted(due, key=lambda row: row[2])  # by fire_at
    for offset_index, offset_str, fire_at in due_sorted:
        if offset_index in consumed:
            continue
        scheduled_iso = fire_at.isoformat()
        if not is_prepared:
            audit.write_event(
                db,
                event_type="session.scheduled_invites_skipped",
                summary=(
                    f"Scheduled invites for {locked.code} skipped "
                    f"({offset_str}): not_prepared"
                ),
                actor_user_id=None,
                session=locked,
                reason="not_prepared",
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

        if abs(delta) > _OFFSET_MAX_MAGNITUDE:
            raise ScheduledActivateError(
                f"Auto-send invite {entry} exceeds the 10-day "
                f"maximum offset magnitude; choose a smaller "
                f"duration."
            )

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
