"""Apply Desk's one clock and its date words (segment AD2B rung 4,
AD-40 and AD-97).

Today is the sample's fixed day while the sample stands: its stages,
outcomes and gates are dated around it (the model exercise is mid
Stage 3, ruling 30). `FROZEN` holds that day; set to None (AD2G, once
stages are stored), today is the wall clock's, in the exercise's own
timezone, so a stage's state turns at its local midnight.

Every page words a date through here:
- `short(d)`: a day within its context's year, "4 Dec";
- `span(a, b)`: a range, its year said once, "1–30 Sep 2026",
  "1 Sep – 4 Dec 2026", "30 Dec 2026 – 4 Jan 2027";
- `stamp(at, zone)`: a stored moment, "2026-08-04 09:12", in the zone.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

#: The sample's today: the day its stages, outcomes and gates are dated around.
SAMPLE_TODAY = date(2026, 11, 17)
#: Today while the sample's dates stand (None: the wall clock's).
FROZEN: date | None = SAMPLE_TODAY


def today(zone: str) -> date:
    """Today, in `zone` (an IANA name)."""
    if FROZEN is not None:
        return FROZEN
    return datetime.now(ZoneInfo(zone)).date()


def midday(zone: str) -> datetime:
    """Midday of today, naive, as the sample's stage dates are."""
    return datetime.combine(today(zone), time(12))


def short(d: date | datetime) -> str:
    """A day as the pages print it inside a dated context, e.g. "4 Dec"."""
    return f"{d.day} {d.strftime('%b')}"


def span(a: date | datetime, b: date | datetime) -> str:
    """A range of days, its year said once (AD-97)."""
    if a.year != b.year:
        return f"{short(a)} {a.year} – {short(b)} {b.year}"
    if a.month != b.month:
        return f"{short(a)} – {short(b)} {b.year}"
    if a.day != b.day:
        return f"{a.day}–{short(b)} {b.year}"
    return f"{short(b)} {b.year}"


def stamp(at: datetime, zone: str) -> str:
    """A stored moment in `zone`, as operator pages print it. A naive
    moment is UTC (SQLite keeps no offset)."""
    aware = at if at.tzinfo else at.replace(tzinfo=UTC)
    return aware.astimezone(ZoneInfo(zone)).strftime("%Y-%m-%d %H:%M")
