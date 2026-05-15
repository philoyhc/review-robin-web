"""Canonical date / time display formatting.

Segment 18B PR 1: one date-time format and one date-only format,
applied through a single pair of helpers so every display site
renders consistently.

Segment 18B PR 2: the helpers grow timezone awareness. A stored
UTC timestamp is converted into a resolved display zone before
formatting. ``tz_name`` defaults to ``UTC`` — callers that pass
nothing (e.g. the email merge fields) keep rendering in UTC.

Segment 18B follow-up: the date-time render dropped its zone token
by default — IANA reports a numeric offset (``+08``) for many zones
and a letter code (``EDT``) for others, so a mixed token read
poorly. Times render bare (``YYYY-MM-DD HH:MM``); which zone they
are in is made explicit on the ``/operator/settings`` and Session
Edit cards instead, via a worked sample.

The token is not gone — it is behind one internal switch,
``SHOW_ZONE_TOKEN`` below. Flip that constant to ``True`` and
restart the app: every display site (the filter reads it on each
call) and the two card previews (the operator Jinja env exposes
it as the ``show_zone_token`` global) append the token again. No
env var, no database migration.

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

# Single internal switch for the trailing zone token on date-time
# renders. Off by default (see the module docstring). Flip to True
# + restart the app to append the resolved zone's ``%Z`` token to
# every ``format_datetime`` render and both timezone-card previews.
SHOW_ZONE_TOKEN = False


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
    """Render a stored UTC datetime as ``YYYY-MM-DD HH:MM``.

    ``value`` is converted from UTC into ``tz_name``'s zone (default
    UTC) before formatting. When ``SHOW_ZONE_TOKEN`` is on, the
    resolved zone's ``%Z`` token is appended (e.g. ``... UTC`` /
    ``... +08``). Returns ``""`` for ``None`` so templates can pipe a
    nullable column through the filter without an ``{% if %}`` guard.
    """
    if value is None:
        return ""
    local = _as_utc(value).astimezone(resolve_zone(tz_name))
    rendered = local.strftime(_DATETIME_FORMAT)
    if SHOW_ZONE_TOKEN:
        rendered = f"{rendered} {local.strftime('%Z')}"
    return rendered


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
