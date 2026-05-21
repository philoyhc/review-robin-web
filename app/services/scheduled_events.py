"""Lazy observer for scheduled session-lifecycle events (Segment 18G).

Per ``spec/lifecycle.md`` §8.2 + §8.3: scheduled events fire on
operator GETs to session-related pages. Each trigger checks its
precondition (§8.2.3), uses ``SELECT … FOR UPDATE`` on the
session row, and is idempotent via the column clear at the end
of a successful fire.

**PR 1A — scaffolding only.** This module ships the lazy-observer
skeleton without any wired triggers. Subsequent PRs register
per-event triggers inside :func:`observe_scheduled_events`:

- PR 1B — scheduled activation
- PR 2A — auto-send invitations
- Parts 3 / 4 / 5 — reminders, auto-archive, scheduled purge

The ``(db, session, now, correlation_id)`` signature is the
contract every trigger consumes.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession


# --------------------------------------------------------------------------- #
# ISO 8601 duration parsing                                                   #
# --------------------------------------------------------------------------- #


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


# --------------------------------------------------------------------------- #
# Offset resolution                                                           #
# --------------------------------------------------------------------------- #


def _ensure_aware_utc(value: datetime) -> datetime:
    """SQLite stores naive timestamps even with ``DateTime(timezone=True)``;
    treat them as UTC for comparison purposes."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


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


# --------------------------------------------------------------------------- #
# Session lock + observer entry point                                         #
# --------------------------------------------------------------------------- #


def lock_session(db: Session, session: ReviewSession) -> ReviewSession:
    """``SELECT … FOR UPDATE`` the session row + return the (refreshed)
    row.

    Used by triggers to prevent two concurrent operator GETs from
    racing the same fire. The Postgres path takes a row-level lock;
    SQLite silently no-ops the ``FOR UPDATE`` (single-writer DB),
    which is acceptable for the dev loop.

    The caller is expected to follow with an **idempotency check**
    on the relevant schedule column inside the same transaction —
    e.g. ``if locked.scheduled_activate_at is None: return`` — so
    that a second racer sees the first racer's commit and bails.
    """
    return db.execute(
        select(ReviewSession)
        .where(ReviewSession.id == session.id)
        .with_for_update()
    ).scalar_one()


def observe_scheduled_events(
    db: Session,
    session: ReviewSession,
    *,
    now: datetime | None = None,
    correlation_id: str | None = None,
) -> None:
    """Lazy observer entry point — called from session-related GETs
    (Session Home, Operations pages, the Sessions lobby).

    Fires any scheduled-event triggers whose fire-time has passed
    and whose preconditions are met. Idempotent and concurrency-safe
    via :func:`lock_session` + each trigger's idempotency check.

    No-op in PR 1A — the scaffolding lands without wired triggers.
    Subsequent PRs register their per-event triggers inside this
    function body; the ``(db, session, now, correlation_id)``
    contract is what each trigger consumes.
    """
    # Resolve ``now`` once up-front so all triggers in this pass see
    # the same clock — avoids racy "fired at slightly different times"
    # within a single observer call.
    _current = now or datetime.now(timezone.utc)
    _ = (db, session, _current, correlation_id)  # consumed by PR 1B+ triggers
