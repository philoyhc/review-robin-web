"""Participants-platform release window + cross-field ordering.

Anchor: ``responses_release_at`` (the moment reviewees / observers
can start viewing collated responses). Close datetime:
``responses_release_until`` (absolute; NULL ⇒ open-ended). S12
retired the original ``release_until_offset`` ISO 8601 duration in
favour of the absolute datetime so the scheduled-close form input
and the operator's Stop release button can write the same column.

The §8.2.2 anchor-null rule applies: ``responses_release_until``
is inert whenever ``responses_release_at`` is NULL — you can't
have an end without a start.

``validate_schedule_ordering`` enforces the inter-field ordering
across the four operator-set schedule datetimes once every
individual parse has succeeded.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.services import date_formatting

from ._shared import ScheduledActivateError, _ensure_aware_utc


def parse_and_validate_responses_release_at(
    raw: str | None,
    *,
    timezone_name: str,
) -> datetime | None:
    """Parse a date-time box's form value into a UTC-aware datetime.

    Returns ``None`` when ``raw`` is empty (operator cleared the
    field). Raises :class:`ScheduledActivateError` on a malformed
    string. Unlike :func:`parse_and_validate_scheduled_activate_at`,
    no minimum-lead-time floor — the operator can backdate Release-
    from to "viewable immediately" (a value already in the past).
    """
    if not raw:
        return None
    try:
        parsed = date_formatting.parse_local_datetime(raw, timezone_name)
    except ValueError as exc:
        raise ScheduledActivateError(
            "Release responses from must be a valid datetime"
        ) from exc
    return _ensure_aware_utc(parsed)


# Cap the viewing window at one year — enough room for any realistic
# review-results retention while still rejecting obvious operator
# typos (a 2030 datetime on a 2026 release).
_RELEASE_WINDOW_MAX = timedelta(days=365)


def parse_and_validate_responses_release_until(
    raw: str | None,
    *,
    timezone_name: str,
    responses_release_at: datetime | None,
) -> datetime | None:
    """Parse a date-time box's form value into a UTC-aware
    datetime for the responses-release close.

    Returns ``None`` when ``raw`` is empty. Raises
    :class:`ScheduledActivateError` on a malformed string, on a value
    that lands at or before ``responses_release_at`` (the window must
    close *after* it opens), or on a value more than
    :data:`_RELEASE_WINDOW_MAX` after ``responses_release_at``.

    When ``responses_release_at`` is ``None`` (anchor-null state per
    §8.2.2), the close is accepted as-is without an ordering /
    magnitude check — the view-time resolver treats the window as
    inert. Persisting an until without an anchor is allowed and
    harmless; the operator may set the anchor later on the same form.
    """
    if not raw:
        return None
    try:
        parsed = date_formatting.parse_local_datetime(raw, timezone_name)
    except ValueError as exc:
        raise ScheduledActivateError(
            "Release responses until must be a valid datetime"
        ) from exc
    parsed_aware = _ensure_aware_utc(parsed)
    if responses_release_at is not None:
        anchor_aware = _ensure_aware_utc(responses_release_at)
        if parsed_aware <= anchor_aware:
            raise ScheduledActivateError(
                "Release responses until must be after Release "
                "responses from."
            )
        if parsed_aware - anchor_aware > _RELEASE_WINDOW_MAX:
            raise ScheduledActivateError(
                f"Release responses until must be within "
                f"{_RELEASE_WINDOW_MAX.days} days of Release responses "
                f"from."
            )
    return parsed_aware


# The four schedule datetimes carry an inherent order:
#
#   scheduled_activate_at  ≤  deadline  ≤  responses_release_at  <  responses_release_until
#
# Each pair is checked only when both members are set — operators may
# leave any subset NULL. The per-field parsers handle parse + their
# own intra-field rules (lead-time floors, magnitude caps); this
# helper sits one layer above them to enforce the inter-field
# ordering once every individual parse has succeeded. Same
# ``ScheduledActivateError`` raised — the route layer translates to
# 422 just like the other validators.
#
# Note ``responses_release_until > responses_release_at`` (strict) is
# already enforced inside ``parse_and_validate_responses_release_until``
# along with the 365-day magnitude check, so the Create route and the
# details card leave ``responses_release_until`` unset here; this
# helper checks it only
# when a caller passes it — the Settings CSV import, which has no
# per-field parser (findings G22).


def validate_schedule_ordering(
    *,
    scheduled_activate_at: datetime | None,
    deadline: datetime | None,
    responses_release_at: datetime | None,
    responses_release_until: datetime | None = None,
) -> None:
    """Cross-field ordering check across the operator-set schedule
    datetimes. No return value — raises
    :class:`ScheduledActivateError` on the first violation. NULL
    values are treated as "no constraint" (pairs with either side
    NULL skip silently)."""
    if (
        scheduled_activate_at is not None
        and deadline is not None
        and _ensure_aware_utc(deadline) < _ensure_aware_utc(
            scheduled_activate_at
        )
    ):
        raise ScheduledActivateError(
            "End must be on or after Start."
        )
    if (
        deadline is not None
        and responses_release_at is not None
        and _ensure_aware_utc(responses_release_at) < _ensure_aware_utc(
            deadline
        )
    ):
        raise ScheduledActivateError(
            "Release responses from must be on or after End — "
            "reviewees can only view results after the review "
            "window closes."
        )
    # With no End, Release from is the review's end (segment 14E,
    # `session_lifecycle.review_end`), so it cannot come before Start: the
    # session would be skipped at Start, its end already past.
    if (
        scheduled_activate_at is not None
        and deadline is None
        and responses_release_at is not None
        and _ensure_aware_utc(responses_release_at)
        < _ensure_aware_utc(scheduled_activate_at)
    ):
        raise ScheduledActivateError(
            "With no End, Release responses from must be on or after "
            "Start: the release ends the review."
        )
    if (
        responses_release_at is not None
        and responses_release_until is not None
        and _ensure_aware_utc(responses_release_until)
        <= _ensure_aware_utc(responses_release_at)
    ):
        raise ScheduledActivateError(
            "Release responses until must be after Release responses from."
        )



#: How far back a release-window crossing is still stamped (segment 14E).
#: A crossing older than this, from before the clock ran or while the app
#: was down, is not backfilled.
STAMP_GRACE = timedelta(days=1)


def _due_release_stamps(session, now: datetime) -> list[tuple[str, str, datetime, str]]:
    """The window's moments crossed within :data:`STAMP_GRACE` of ``now``
    while the window can be open, as ``(event_type, context key, moment,
    word)``. No query.

    The window opens only on an ``expired`` session
    (``session_lifecycle.is_response_release_window_open``), so nothing is
    due on any other: a Release-from that passes while the session is
    still open stamps nothing, and is stamped when the operator ends the
    session, if within the grace."""
    if session.status != "expired":
        return []
    start = session.responses_release_at
    if start is None:
        return []
    start = _ensure_aware_utc(start)
    due = []
    if now - STAMP_GRACE < start <= now:
        due.append(("session.release_window_opened", "release_at", start, "opened"))
    until = session.responses_release_until
    if until is not None:
        until = _ensure_aware_utc(until)
        if start < until and now - STAMP_GRACE < until <= now:
            due.append(("session.release_window_ended", "release_until", until, "ended"))
    return due


def _unstamped(db, session, due):
    """The due moments not yet in the audit log."""
    from sqlalchemy import select

    from app.db.models import AuditEvent

    out = []
    for event_type, key, moment, word in due:
        iso = moment.isoformat()
        stamped = any(
            ((detail or {}).get("context") or {}).get(key) == iso
            for detail in db.execute(
                select(AuditEvent.detail).where(
                    AuditEvent.session_id == session.id,
                    AuditEvent.event_type == event_type,
                )
            ).scalars()
        )
        if not stamped:
            out.append((event_type, key, iso, word))
    return out


def observe_release_window(
    db,
    session,
    *,
    now: datetime,
    correlation_id: str | None = None,
) -> int:
    """Stamp the release window's start and end in the audit log, once
    per crossing (segment 14E; author, 2026-11-04): a
    ``session.release_window_opened`` when ``responses_release_at`` has
    passed, a ``session.release_window_ended`` when
    ``responses_release_until`` has, each within :data:`STAMP_GRACE` of
    ``now`` and only while the session is ``expired``, the one state in
    which the window opens. A moment already stamped is not stamped
    again, whichever trigger (clock or page view) reaches it first; a
    moved moment is a new crossing. Returns the number written, and
    commits only when it writes.

    Checks without a lock first, as the other triggers do, so a page
    view after the stamps exist takes no lock. Changes nothing about
    what is visible: the window is still checked on arrival.
    """
    due = _due_release_stamps(session, now)
    if not due or not _unstamped(db, session, due):
        return 0
    from app.services import audit
    from app.services.session_guard import lock_session

    # Under the session lock, so two triggers reaching one crossing at
    # once stamp it once; the window is read again on the locked row.
    locked = lock_session(db, session)
    written = 0
    for event_type, key, iso, word in _unstamped(
        db, locked, _due_release_stamps(locked, now)
    ):
        audit.write_event(
            db,
            event_type=event_type,
            summary=f"Release window {word}",
            actor_user_id=None,
            session=locked,
            context={key: iso},
            correlation_id=correlation_id,
        )
        written += 1
    if written:
        db.commit()
    return written
