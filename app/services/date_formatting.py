"""Canonical date / time display formatting.

Segment 18B PR 1: one date-time format and one date-only format,
applied through a single pair of helpers so every display site
renders consistently.

Segment 18B PR 2: the helpers grow timezone awareness. A stored
UTC timestamp is converted into a resolved display zone before
formatting. ``tz_name`` defaults to ``UTC`` for a caller that passes
nothing; the email merge fields pass the session's zone.

Segment 18B follow-up: the date-time render dropped its zone token
by default — IANA reports a numeric offset (``+08``) for many zones
and a letter code (``EDT``) for others, so a mixed token read
poorly. Times render bare (``YYYY-MM-DD HH:MM``); which zone they
are in is made explicit on the ``/operator/settings`` and Session
Edit cards instead, via a worked sample.

The token is not gone — it is behind one internal switch,
``SHOW_ZONE_TOKEN`` below. Flip that constant to ``True`` and
restart the app: every display site (the filter reads it on each
call) and the ``/operator/settings`` card preview (the operator
Jinja env exposes it as the ``show_zone_token`` global) append the
token again. No
env var, no database migration.

The per-render zone is resolved upstream (``app/web/date_filters.py``
context processor + the ``display_timezone`` Jinja context key);
these helpers only take the resolved zone name.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


_DATETIME_FORMAT = "%Y-%m-%d %H:%M"
_DATE_FORMAT = "%Y-%m-%d"

DEFAULT_TIMEZONE = "UTC"

# Single internal switch for the trailing zone token on date-time
# renders. Off by default (see the module docstring). Flip to True
# + restart the app to append the resolved zone's ``%Z`` token to
# every ``format_datetime`` render and both timezone-card previews.
SHOW_ZONE_TOKEN = False

# How close to the edge of ``datetime``'s range an entered instant may
# sit (findings L2). Every zone's offset is under a day, so an instant
# inside this margin converts into any zone without overflowing.
_CALENDAR_MARGIN = timedelta(days=1)
_EARLIEST_INSTANT = datetime.min + _CALENDAR_MARGIN
_LATEST_INSTANT = datetime.max - _CALENDAR_MARGIN


def in_entry_range(value: datetime) -> bool:
    """Whether ``value`` sits inside the range an entered instant may
    take: a day clear of either edge of ``datetime``'s range, so it
    converts into any zone (findings L2). Naive values are UTC."""
    try:
        instant = _as_utc(value).replace(tzinfo=None)
    except OverflowError:
        return False
    return _EARLIEST_INSTANT <= instant <= _LATEST_INSTANT


def _as_utc(value: datetime) -> datetime:
    """Normalise a datetime to tz-aware UTC.

    Naive values are assumed UTC — every stored timestamp in the app
    is UTC, and SQLite returns them naive.
    """
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _converts(value: datetime, tz_name: str | None) -> bool:
    """Whether ``value`` converts into ``tz_name``'s zone without leaving
    ``datetime``'s range."""
    try:
        _as_utc(value).astimezone(resolve_zone(tz_name))
    except OverflowError:
        return False
    return True


def _in_zone(value: datetime, tz_name: str | None) -> datetime:
    """A stored datetime converted into ``tz_name``'s zone, or left in
    UTC when that conversion would leave ``datetime``'s range: an
    instant stored at the calendar's edge renders unconverted rather
    than raising (findings L2)."""
    utc = _as_utc(value)
    try:
        return utc.astimezone(resolve_zone(tz_name))
    except OverflowError:
        return utc


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
    local = _in_zone(value, tz_name)
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
        value = _in_zone(value, tz_name).date()
    return value.strftime(_DATE_FORMAT)


def gmt_offset_label(tz_name: str | None, at: datetime | None = None) -> str:
    """Compact GMT-offset label for an IANA zone — e.g. ``Asia/Singapore``
    becomes ``GMT+8``, ``Asia/Kolkata`` ``GMT+5:30``, and a zero offset
    (``UTC``) becomes ``UTC``.

    Far narrower than the raw IANA id for the sessions-lobby Timezone
    column. ``at`` selects the standard / daylight offset variant; with
    ``at`` unset the current moment is used.
    """
    zone = resolve_zone(tz_name)
    reference = datetime.now(zone)
    if at is not None:
        try:
            reference = _as_utc(at).astimezone(zone)
        except OverflowError:
            # An instant at the calendar's edge renders in UTC, so its
            # label says UTC (findings L2).
            return "UTC"
    offset = reference.utcoffset()
    if offset is None or offset == timedelta(0):
        return "UTC"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    hours, minutes = divmod(abs(total_minutes), 60)
    if minutes:
        return f"GMT{sign}{hours}:{minutes:02d}"
    return f"GMT{sign}{hours}"


def gmt_offset_zone_label(tz_name: str | None, at: datetime | None = None) -> str:
    """The compact GMT-offset followed by the raw IANA zone id — e.g.
    ``Asia/Singapore`` becomes ``GMT+8 Asia/Singapore``.

    The display form for zone identity across the app: an at-a-glance
    offset for orientation, the unambiguous IANA id for precision. When
    the two would be redundant (a bare ``UTC``) only one is shown.
    ``at`` selects the standard / daylight offset variant.
    """
    zone = tz_name or DEFAULT_TIMEZONE
    offset = gmt_offset_label(tz_name, at)
    if at is not None and not _converts(at, tz_name):
        # Rendered in UTC (findings L2), so labelled UTC alone.
        return "UTC"
    if offset == zone:
        return zone
    return f"{offset} {zone}"


def parse_local_datetime(value: str, tz_name: str | None) -> datetime:
    """Parse a date-time box's text (``YYYY-MM-DD HH:MM``, or a browser
    ``datetime-local`` string's ``YYYY-MM-DDTHH:MM``) as wall-clock in
    ``tz_name``'s zone and return the equivalent UTC instant, naive
    (matching how stored timestamps are kept).

    Raises ``ValueError`` for an unparseable string — callers turn
    that into a 4xx. Segment 18B PR 4. A moment within a day of the
    edge of ``datetime``'s range is refused the same way: converting
    it, now or for display in another zone, would overflow
    (findings L2).
    """
    naive = datetime.fromisoformat(value)
    local = naive.replace(tzinfo=resolve_zone(tz_name))
    if not in_entry_range(local):
        raise ValueError(f"datetime out of range: {value!r}")
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def iso_in_zone(
    value: datetime | None, tz_name: str | None, *, timespec: str = "auto"
) -> str:
    """ISO 8601 rendering of a stored UTC datetime, converted into
    ``tz_name``'s zone so the trailing offset reflects that zone —
    e.g. ``2026-06-02T08:00:00+08:00``. ``""`` for ``None``.

    Used by the per-session CSV extracts: a precise, round-trip-safe
    machine format whose offset names the session zone. Segment 18B.
    ``timespec`` is ``datetime.isoformat``'s; pass ``"microseconds"``
    for a fixed-width string that sorts as text.
    """
    if value is None:
        return ""
    return _in_zone(value, tz_name).isoformat(timespec=timespec)


def format_datetime_box(value: datetime | None, tz_name: str | None) -> str:
    """Render a stored UTC datetime as a date-time field's text
    (``YYYY-MM-DD HH:MM``, 24-hour) in ``tz_name``'s zone: the text box
    of a date-time field (segment 19X Item 6), the displays' format
    without a zone token. ``""`` for ``None``.
    :func:`parse_local_datetime` reads it back."""
    if value is None:
        return ""
    return _in_zone(value, tz_name).strftime(_DATETIME_FORMAT)


def box_text(value: str | None) -> str:
    """A date-time box's submitted text with ``T`` or a space between
    date and time read alike, so a native ``datetime-local`` value and
    the text box's compare as one (19X Item 6). Surrounding space is
    dropped; any other text is returned as it came."""
    text = (value or "").strip()
    if len(text) > 10 and text[10] == "T":
        text = f"{text[:10]} {text[11:]}"
    return text


def format_datetime_local(
    value: datetime | None, tz_name: str | None
) -> str:
    """Render a stored UTC datetime as a browser ``datetime-local``
    value (``YYYY-MM-DDTHH:MM``) in ``tz_name``'s zone — the inverse
    of :func:`parse_local_datetime`, used to pre-fill a deadline
    picker. ``""`` for ``None``. Segment 18B PR 5.
    """
    if value is None:
        return ""
    return _in_zone(value, tz_name).strftime("%Y-%m-%dT%H:%M")
