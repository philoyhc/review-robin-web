"""The sends due by hand while scheduled email is off (14F rung 5b).

With ``RRW_SCHEDULED_SEND`` off nothing is sent on a clock, and the
invite and reminder offsets the operator set time **prompts** instead
(author, 2026-11-06). An entry is due when:

- its moment (Start or End plus its offset) has passed;
- there is someone left to act on: a prepared session with invitations
  still to send, or an activated one with reviewers still incomplete;
- it is not already recorded on its anchor, as sent, skipped or
  **handled** — the operator's *Mark as done*.

*Mark as done* writes ``session.scheduled_invites_handled`` /
``session.scheduled_reminders_handled`` with the observers' context
(``anchor_at`` / ``offset_index`` / ``offset``), and those are among the
event types ``scheduled_events.fired_offsets`` reads. So a handled entry
is consumed on its anchor exactly as a sent one is: 14G's observers,
once sending is on, never send it again, and a save may not put a
different entry on its position.

With scheduled email on, nothing is due here: the observers send. Nor is
anything due on a session whose linked application takes the email lock
(segment 23F): that application sends its own mail, so Review Robin has
nothing to prompt. Every reader of a due entry, the Workflow card and the
lobby's Due pill alike, gets that from here (findings 2026-11-20, D1).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession, User
from app.json_shapes import json_list
from app.services import audit, invitations, linked_apps, scheduled_events
from app.services import session_lifecycle as lifecycle

#: Per kind: the offsets column, the anchor column, the event *Mark as
#: done* writes.
_KINDS = {
    "invite": ("invite_offsets", "scheduled_activate_at", "session.scheduled_invites_handled"),
    "reminder": ("reminder_offsets", "deadline", "session.scheduled_reminders_handled"),
}
KINDS = tuple(_KINDS)


@dataclass(frozen=True)
class DueAction:
    """One offset entry whose prompt is due."""

    kind: str
    offset_index: int
    offset: str
    due_at: datetime
    anchor_at: datetime
    #: Invitations still to send, or reviewers still incomplete.
    count: int


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _can_act_on(review_session: ReviewSession, kind: str) -> bool:
    """Whether ``kind`` can have anything left in the session's state:
    invites while prepared, reminders while activated."""
    if kind == "invite":
        return lifecycle.is_validated(review_session) or lifecycle.is_ready(review_session)
    return lifecycle.is_ready(review_session)


def _left_to_act_on(db: Session, review_session: ReviewSession, kind: str) -> int:
    """Invitations still to send (prepared), or reviewers with an
    invitation still incomplete (activated) — the set Remind incomplete
    reminds, whether or not that invitation was ever sent, since the
    operator may have shared the link instead; 0 outside those states."""
    if not _can_act_on(review_session, kind):
        return 0
    if kind == "invite":
        return len(invitations.list_sendable_invitations(db, review_session.id))
    from app.services import monitoring  # local, as invitations does: a circular import

    return sum(
        1
        for row in monitoring.per_reviewer_progress(db, review_session)
        if row.is_incomplete and row.invitation is not None
    )


def due_actions(
    db: Session, review_session: ReviewSession, *, now: datetime | None = None
) -> list[DueAction]:
    """The entries due on ``review_session`` now, earliest first; none
    while scheduled email is on, and none where a linked application
    takes the email lock.

    The lobby asks this of every session it lists (findings 2026-11-20
    assessment N1), so what needs no query is asked first: an anchor and
    offsets, a state the kind can act in, an entry whose moment has
    passed. The audit read of handled entries, then the count of what is
    left, run only for a session that still has one due."""
    if scheduled_events.scheduled_send_enabled():
        return []
    if linked_apps.locks(review_session, linked_apps.Lock.EMAIL):
        return []
    moment = _aware(now or datetime.now(UTC))
    due: list[DueAction] = []
    for kind, (column, anchor_column, _event) in _KINDS.items():
        anchor = getattr(review_session, anchor_column)
        offsets = json_list(getattr(review_session, column) or []) or []
        if anchor is None or not offsets or not _can_act_on(review_session, kind):
            continue
        anchor = _aware(anchor)
        passed: list[tuple[int, str, datetime]] = []
        for index, raw in enumerate(offsets):
            if not isinstance(raw, str):
                continue
            try:
                at = anchor + scheduled_events.parse_iso_duration(raw)
            except ValueError:
                continue
            if at <= moment:
                passed.append((index, raw, at))
        if not passed:
            continue
        consumed = scheduled_events.fired_offsets(db, review_session, kind, anchor)
        entries = [entry for entry in passed if entry[0] not in consumed]
        if not entries:
            continue
        count = _left_to_act_on(db, review_session, kind)
        if count == 0:
            continue
        due.extend(DueAction(kind, index, raw, at, anchor, count) for index, raw, at in entries)
    return sorted(due, key=lambda action: action.due_at)


def _same_instant(anchor: datetime, posted: str) -> bool:
    try:
        return _aware(datetime.fromisoformat(posted)) == anchor
    except ValueError:
        return False


class NotDue(Exception):
    """*Mark as done* on an entry that is not due: already handled, its
    offset or anchor changed since the page was drawn, sending is on, or a
    linked application takes the email lock."""


def mark_done(
    db: Session,
    review_session: ReviewSession,
    *,
    kind: str,
    offset_index: int,
    offset: str,
    anchor_at: str,
    user: User,
    correlation_id: str | None = None,
) -> DueAction:
    """Record a due entry as handled, under the session lock, so its
    prompt clears and 14G never sends it. Raises :class:`NotDue`.

    The entry is named by everything the prompt was drawn from — its
    kind, position, offset and anchor (ISO 8601) — so a form from a page
    drawn before another tab moved End or replaced the offset is refused
    rather than marking the entry now at that position (Codex on #3668)."""
    if kind not in _KINDS:
        raise NotDue()
    locked = scheduled_events.lock_session(db, review_session)
    action = next(
        (
            a
            for a in due_actions(db, locked)
            if a.kind == kind
            and a.offset_index == offset_index
            and a.offset == offset
            and _same_instant(a.anchor_at, anchor_at)
        ),
        None,
    )
    if action is None:
        db.rollback()
        raise NotDue()
    audit.write_event(
        db,
        event_type=_KINDS[kind][2],
        summary=(
            f"{'Invites' if kind == 'invite' else 'Reminders'} for {locked.code} "
            f"marked done ({action.offset})"
        ),
        actor_user_id=user.id,
        session=locked,
        context={
            "anchor_at": action.anchor_at.isoformat(),
            "offset_index": action.offset_index,
            "offset": action.offset,
            "scheduled_at": action.due_at.isoformat(),
        },
        correlation_id=correlation_id,
    )
    db.commit()
    return action


#: The scheduled-activation failure that gives up (18G Part 1), the one
#: other thing the lobby's Due pill reports (14F rung 5c).
ACTIVATION_GAVE_UP = "session.scheduled_activation_failed_persistent"


def sessions_with_something_due(
    db: Session, review_sessions: Sequence[ReviewSession]
) -> frozenset[int]:
    """The ids of the sessions with a due prompt, or whose scheduled
    activation gave up and nothing has happened on them since: the most
    recent audit row is still that failure, the rule the Workflow card's
    caption uses."""
    flagged = {rs.id for rs in review_sessions if due_actions(db, rs)}
    candidates = [rs.id for rs in review_sessions if not lifecycle.is_ready(rs)]
    if candidates:
        latest = (
            select(AuditEvent.session_id, func.max(AuditEvent.id).label("latest_id"))
            .where(AuditEvent.session_id.in_(candidates))
            .group_by(AuditEvent.session_id)
            .subquery()
        )
        gave_up = db.execute(
            select(AuditEvent.session_id)
            .join(latest, AuditEvent.id == latest.c.latest_id)
            .where(AuditEvent.event_type == ACTIVATION_GAVE_UP)
        ).scalars()
        flagged.update(sid for sid in gave_up if sid is not None)
    return frozenset(flagged)
