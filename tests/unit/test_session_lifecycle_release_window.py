"""Unit tests for ``session_lifecycle.is_response_release_window_open``.

Pins the predicate spelled out in
``spec/visibility_policy.md`` §3.2: the after-release window
is open iff the anchor (``responses_release_at``) is set and
reached, and the close (``responses_release_until``) is either
NULL (open-ended) or hasn't yet arrived. Anchor-null reads as
inert (window closed) regardless of any saved close datetime.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.models import ReviewSession
from app.services.session_lifecycle import (
    is_response_release_window_open,
)


def _at(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day, tzinfo=timezone.utc)


def _session(
    *,
    release_at: datetime | None,
    release_until: datetime | None = None,
) -> ReviewSession:
    """Build a bare ``ReviewSession`` instance for the predicate;
    not added to a Session — the helper only reads attributes."""
    return ReviewSession(
        name="S",
        code="rw",
        responses_release_at=release_at,
        responses_release_until=release_until,
    )


def test_anchor_null_reads_as_closed_regardless_of_until() -> None:
    """``responses_release_at`` NULL is the inert / anchor-null
    rule — the window is closed until the operator sets it."""
    session = _session(
        release_at=None, release_until=_at(2030, 1, 1)
    )
    assert not is_response_release_window_open(
        session, now=_at(2026, 1, 1)
    )


def test_before_anchor_reads_as_closed() -> None:
    session = _session(release_at=_at(2026, 6, 15))
    assert not is_response_release_window_open(
        session, now=_at(2026, 6, 14)
    )


def test_at_anchor_reads_as_open() -> None:
    session = _session(release_at=_at(2026, 6, 15))
    assert is_response_release_window_open(
        session, now=_at(2026, 6, 15)
    )


def test_after_anchor_with_no_until_reads_as_open() -> None:
    """Open-ended (``responses_release_until`` NULL) — the
    window stays open indefinitely once the anchor passes."""
    session = _session(release_at=_at(2026, 6, 15))
    assert is_response_release_window_open(
        session, now=_at(2030, 1, 1)
    )


def test_after_anchor_before_until_reads_as_open() -> None:
    session = _session(
        release_at=_at(2026, 6, 15),
        release_until=_at(2026, 7, 15),
    )
    assert is_response_release_window_open(
        session, now=_at(2026, 7, 1)
    )


def test_at_until_reads_as_closed() -> None:
    """``until`` is the half-open close — the window shuts the
    instant ``now`` hits it."""
    session = _session(
        release_at=_at(2026, 6, 15),
        release_until=_at(2026, 7, 15),
    )
    assert not is_response_release_window_open(
        session, now=_at(2026, 7, 15)
    )


def test_after_until_reads_as_closed() -> None:
    session = _session(
        release_at=_at(2026, 6, 15),
        release_until=_at(2026, 7, 15),
    )
    assert not is_response_release_window_open(
        session, now=_at(2026, 7, 16)
    )


def test_default_now_defers_to_current_time() -> None:
    """When ``now`` isn't passed, the predicate falls back to
    ``datetime.now(timezone.utc)`` — exercise the live-time path
    by setting an anchor far enough in the past that the call
    can't race with any plausible test machine clock."""
    session = _session(release_at=datetime(2000, 1, 1, tzinfo=timezone.utc))
    assert is_response_release_window_open(session)

    future_session = _session(
        release_at=datetime.now(timezone.utc) + timedelta(days=365)
    )
    assert not is_response_release_window_open(future_session)
