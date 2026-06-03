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
    """Parse a ``datetime-local`` form value into a UTC-aware datetime.

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
    """Parse a ``datetime-local`` form value into a UTC-aware
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
# along with the 365-day magnitude check; this helper handles the two
# remaining pairs (``End ≥ Start``, ``Release-from ≥ End``).


def validate_schedule_ordering(
    *,
    scheduled_activate_at: datetime | None,
    deadline: datetime | None,
    responses_release_at: datetime | None,
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
