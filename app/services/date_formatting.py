"""Canonical date / time display formatting.

Segment 18B PR 1: one date-time format and one date-only format,
applied through a single pair of helpers so every display site
renders consistently.

Segment 18B PR 2: the helpers grow timezone awareness. A stored
UTC timestamp is converted into a resolved display zone before
formatting, and the date-time render carries the resolved zone's
abbreviation token (``%Z``) so a value is never read against the
wrong zone. ``tz_name`` defaults to ``UTC`` — callers that pass
nothing (e.g. the email merge fields) keep rendering in UTC.

The per-render zone is resolved upstream (``app/web/date_filters.py``
context processor + the ``display_timezone`` Jinja context key);
these helpers only take the resolved zone name.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_DATETIME_FORMAT = "%Y-%m-%d %H:%M"
_DATE_FORMAT = "%Y-%m-%d"

DEFAULT_TIMEZONE = "UTC"


def _as_utc(value: datetime) -> datetime:
    """Normalise a datetime to tz-aware UTC.

    Naive values are assumed UTC — every stored timestamp in the app
    is UTC, and SQLite returns them naive.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def resolve_zone(tz_name: str | None) -> ZoneInfo:
    """Return the ``ZoneInfo`` for an IANA zone name, falling back to
    UTC for an unset / unknown name so a display site never raises."""
    if not tz_name:
        return ZoneInfo(DEFAULT_TIMEZONE)
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo(DEFAULT_TIMEZONE)


def format_datetime(value: datetime | None, tz_name: str | None = None) -> str:
    """Render a stored UTC datetime as ``YYYY-MM-DD HH:MM <ZONE>``.

    ``value`` is converted from UTC into ``tz_name``'s zone (default
    UTC) and the resolved zone's abbreviation is appended — e.g.
    ``2026-05-15 17:00 UTC`` or ``2026-05-15 17:00 +08``. Returns
    ``""`` for ``None`` so templates can pipe a nullable column
    through the filter without an ``{% if %}`` guard.
    """
    if value is None:
        return ""
    local = _as_utc(value).astimezone(resolve_zone(tz_name))
    return f"{local.strftime(_DATETIME_FORMAT)} {local.strftime('%Z')}"


def format_date(
    value: date | datetime | None, tz_name: str | None = None
) -> str:
    """Render a date (or the date part of a datetime) as ``YYYY-MM-DD``.

    For a datetime, the calendar date is taken in ``tz_name``'s zone
    (default UTC) — so a timestamp near midnight lands on the right
    day for the display zone.
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = _as_utc(value).astimezone(resolve_zone(tz_name)).date()
    return value.strftime(_DATE_FORMAT)
