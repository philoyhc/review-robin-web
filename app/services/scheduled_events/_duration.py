"""ISO 8601 duration parsing + anchor / offset resolution."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from app.db.models import ReviewSession

from ._shared import _ensure_aware_utc


_ISO_DURATION_RE = re.compile(
    r"^(?P<sign>-)?P"
    r"(?:(?P<years>\d+)Y)?"
    r"(?:(?P<months>\d+)M)?"
    r"(?:(?P<days>\d+)D)?"
    r"(?:T"
    r"(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+)S)?"
    r")?$"
)


def parse_iso_duration(text: str) -> timedelta:
    """Parse an ISO 8601 duration string into a :class:`datetime.timedelta`.

    Accepts the standard designators only
    (``P[n]Y[n]M[n]DT[n]H[n]M[n]S``), with an optional leading minus
    sign for negative durations. Fractional values and weeks (``P1W``)
    are rejected per ``spec/lifecycle.md`` §8.2.4.

    Years and months are approximated: 1Y = 365d, 1M = 30d. Scheduled
    offsets in practice use only days / hours / minutes / seconds, so
    the approximation rarely matters; documented here so callers can
    avoid feeding years / months into a precision-sensitive context.
    """
    match = _ISO_DURATION_RE.fullmatch(text.strip())
    if match is None:
        raise ValueError(f"not an ISO 8601 duration: {text!r}")
    parts = match.groupdict()
    body_keys = ("years", "months", "days", "hours", "minutes", "seconds")
    if all(parts[k] is None for k in body_keys):
        raise ValueError(f"empty ISO 8601 duration: {text!r}")
    years = int(parts["years"] or 0)
    months = int(parts["months"] or 0)
    days = int(parts["days"] or 0)
    hours = int(parts["hours"] or 0)
    minutes = int(parts["minutes"] or 0)
    seconds = int(parts["seconds"] or 0)
    total = timedelta(
        days=years * 365 + months * 30 + days,
        hours=hours,
        minutes=minutes,
        seconds=seconds,
    )
    if parts["sign"] == "-":
        total = -total
    return total


def resolve_offset(
    session: ReviewSession,
    anchor_field: str,
    offset_field: str,
) -> datetime | None:
    """Resolve an anchor + offset pair into an absolute fire datetime.

    Returns ``None`` when either the anchor column or the offset
    column is null — the §8.2.2 anchor-null inertness rule. Also
    returns ``None`` when the offset string fails to parse, so the
    caller doesn't need to wrap each call in a try/except; the
    trigger should audit the malformed value via a separate path.

    Otherwise returns ``anchor + parse_iso_duration(offset)`` as a
    timezone-aware datetime.
    """
    anchor = getattr(session, anchor_field, None)
    offset = getattr(session, offset_field, None)
    if anchor is None or offset is None:
        return None
    try:
        delta = parse_iso_duration(offset)
    except ValueError:
        return None
    return _ensure_aware_utc(anchor) + delta
