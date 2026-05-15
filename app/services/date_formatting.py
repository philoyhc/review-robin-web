"""Canonical date / time display formatting.

Segment 18B PR 1: one date-time format and one date-only format,
applied through a single pair of helpers so every display site
renders consistently.

All stored timestamps are UTC (naive on SQLite, tz-aware on
Postgres); the helpers normalise to UTC before formatting and the
date-time render carries an explicit ``UTC`` zone token so a value
is never read against the wrong zone.

Timezone resolution — rendering in a per-session / deployment-default
zone rather than UTC — lands in 18B PR 2 / PR 3. Until then every
render is UTC.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

_DATETIME_FORMAT = "%Y-%m-%d %H:%M"
_DATE_FORMAT = "%Y-%m-%d"


def _as_utc(value: datetime) -> datetime:
    """Normalise a datetime to tz-aware UTC.

    Naive values are assumed UTC — every stored timestamp in the app
    is UTC, and SQLite returns them naive.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def format_datetime(value: datetime | None) -> str:
    """Render a stored UTC datetime as ``YYYY-MM-DD HH:MM UTC``.

    Returns ``""`` for ``None`` so templates can pipe a nullable
    column through the filter without an ``{% if %}`` guard.
    """
    if value is None:
        return ""
    return f"{_as_utc(value).strftime(_DATETIME_FORMAT)} UTC"


def format_date(value: date | datetime | None) -> str:
    """Render a date (or the date part of a datetime) as ``YYYY-MM-DD``."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = _as_utc(value).date()
    return value.strftime(_DATE_FORMAT)
