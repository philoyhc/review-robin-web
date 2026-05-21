"""Unit tests for the Segment 18G lazy-observer scaffolding (PR 1A).

The module ships without wired triggers — these tests cover the
shared helpers (``parse_iso_duration``, ``resolve_offset``,
``lock_session``) and the no-op entry point. Per-trigger coverage
lands with each consumer PR (1B activation, 2A invites, …).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services import scheduled_events


# --------------------------------------------------------------------------- #
# parse_iso_duration                                                          #
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("P30D", timedelta(days=30)),
        ("PT2H", timedelta(hours=2)),
        ("PT4H30M", timedelta(hours=4, minutes=30)),
        ("PT240H", timedelta(hours=240)),
        ("P1DT12H", timedelta(days=1, hours=12)),
        ("-P1D", timedelta(days=-1)),
        ("-PT2H", timedelta(hours=-2)),
        ("-PT240H", timedelta(hours=-240)),
        ("P1Y", timedelta(days=365)),  # year approximation
        ("P2M", timedelta(days=60)),   # month approximation
    ],
)
def test_parse_iso_duration_valid_forms(text: str, expected: timedelta) -> None:
    assert scheduled_events.parse_iso_duration(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "PT",
        "P",
        "P1W",  # weeks rejected
        "P1.5D",  # fractional rejected
        "PT2.5H",
        "1D",  # missing P prefix
        "garbage",
        "P 1D",  # whitespace inside body
        "P1D2H",  # missing T separator
    ],
)
def test_parse_iso_duration_rejects_invalid(text: str) -> None:
    with pytest.raises(ValueError):
        scheduled_events.parse_iso_duration(text)


def test_parse_iso_duration_trims_outer_whitespace() -> None:
    """Outer whitespace is trimmed; the parser is forgiving of CSV-round-tripped values."""
    assert scheduled_events.parse_iso_duration("  PT1H  ") == timedelta(hours=1)


# --------------------------------------------------------------------------- #
# resolve_offset                                                              #
# --------------------------------------------------------------------------- #


def _make_session(db: Session, code: str, **kwargs: object) -> ReviewSession:
    op = User(email=f"op-{code}@example.edu", display_name="Op")
    db.add(op)
    db.flush()
    review_session = ReviewSession(
        name=code.title(), code=code, created_by_user_id=op.id, **kwargs
    )
    db.add(review_session)
    db.flush()
    return review_session


def test_resolve_offset_anchor_null_returns_none(db: Session) -> None:
    review_session = _make_session(
        db, "anchor-null", invite_offsets=["-P1D"]
    )
    # scheduled_activate_at is unset
    assert (
        scheduled_events.resolve_offset(
            review_session, "scheduled_activate_at", "invite_offsets"
        )
        is None
    )


def test_resolve_offset_offset_null_returns_none(db: Session) -> None:
    when = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    review_session = _make_session(
        db, "offset-null", scheduled_activate_at=when
    )
    # archive_offset is unset
    assert (
        scheduled_events.resolve_offset(
            review_session, "deadline", "archive_offset"
        )
        is None
    )


def test_resolve_offset_both_null_returns_none(db: Session) -> None:
    review_session = _make_session(db, "both-null")
    assert (
        scheduled_events.resolve_offset(
            review_session, "scheduled_activate_at", "invite_offsets"
        )
        is None
    )


def test_resolve_offset_valid_anchor_string_offset(db: Session) -> None:
    """Singleton offset string (archive_offset) anchored on deadline."""
    deadline = datetime(2026, 6, 1, 17, 0, tzinfo=timezone.utc)
    review_session = _make_session(
        db, "valid-archive", deadline=deadline, archive_offset="P30D"
    )

    resolved = scheduled_events.resolve_offset(
        review_session, "deadline", "archive_offset"
    )
    assert resolved == deadline + timedelta(days=30)


def test_resolve_offset_negative_duration_subtracts(db: Session) -> None:
    """A negative ISO 8601 duration moves the fire moment *before* the anchor."""
    start = datetime(2026, 6, 1, 9, 0, tzinfo=timezone.utc)
    review_session = _make_session(
        db, "valid-negative", scheduled_activate_at=start, archive_offset="-P1D"
    )

    # Using archive_offset against scheduled_activate_at as the anchor for
    # this test, since invite_offsets is a JSON list and resolve_offset
    # consumes scalar strings. Anchor + ``-P1D`` = anchor - 1 day.
    resolved = scheduled_events.resolve_offset(
        review_session, "scheduled_activate_at", "archive_offset"
    )
    assert resolved == start - timedelta(days=1)


def test_resolve_offset_invalid_duration_returns_none(db: Session) -> None:
    """Malformed offset short-circuits to None — caller doesn't need a try/except."""
    deadline = datetime(2026, 6, 1, 17, 0, tzinfo=timezone.utc)
    review_session = _make_session(
        db, "invalid-offset", deadline=deadline, archive_offset="not-a-duration"
    )

    assert (
        scheduled_events.resolve_offset(
            review_session, "deadline", "archive_offset"
        )
        is None
    )


def test_resolve_offset_naive_anchor_treated_as_utc(db: Session) -> None:
    """A naive datetime on the anchor column (SQLite default) is treated as UTC."""
    naive_deadline = datetime(2026, 6, 1, 17, 0)  # no tzinfo
    review_session = _make_session(
        db, "naive-anchor", archive_offset="P1D"
    )
    review_session.deadline = naive_deadline
    db.flush()

    resolved = scheduled_events.resolve_offset(
        review_session, "deadline", "archive_offset"
    )
    assert resolved is not None
    assert resolved.tzinfo is not None
    assert resolved == datetime(2026, 6, 2, 17, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# lock_session                                                                #
# --------------------------------------------------------------------------- #


def test_lock_session_returns_refreshed_row(db: Session) -> None:
    """The lock helper round-trips the same session row. On SQLite the
    FOR UPDATE clause is a silent no-op; on Postgres it acquires a
    row-level lock. Either way the returned row is the canonical
    refreshed instance."""
    review_session = _make_session(db, "lock-roundtrip")

    locked = scheduled_events.lock_session(db, review_session)
    assert locked.id == review_session.id
    assert locked.code == review_session.code


# --------------------------------------------------------------------------- #
# observe_scheduled_events                                                    #
# --------------------------------------------------------------------------- #


def test_observe_scheduled_events_is_no_op_in_pr_1a(db: Session) -> None:
    """PR 1A ships the scaffolding without any wired triggers; calling
    the observer on any session is a no-op and writes no audit events."""
    from app.db.models import AuditEvent
    from sqlalchemy import func, select

    review_session = _make_session(db, "no-op")

    before = db.execute(
        select(func.count()).select_from(AuditEvent).where(
            AuditEvent.session_id == review_session.id
        )
    ).scalar()
    assert before == 0

    scheduled_events.observe_scheduled_events(db, review_session)
    db.flush()

    after = db.execute(
        select(func.count()).select_from(AuditEvent).where(
            AuditEvent.session_id == review_session.id
        )
    ).scalar()
    assert after == 0


def test_observe_scheduled_events_accepts_explicit_now(db: Session) -> None:
    """The ``now`` kwarg lets callers (and tests) pin the clock — used
    by per-trigger tests once triggers are wired."""
    review_session = _make_session(db, "explicit-now")
    pinned = datetime(2099, 1, 1, tzinfo=timezone.utc)

    # No-op, but should accept the kwarg without raising.
    scheduled_events.observe_scheduled_events(db, review_session, now=pinned)


def test_observe_scheduled_events_accepts_correlation_id(db: Session) -> None:
    """The ``correlation_id`` kwarg is consumed by future triggers'
    audit events; the no-op accepts it without raising."""
    review_session = _make_session(db, "with-corr-id")
    scheduled_events.observe_scheduled_events(
        db, review_session, correlation_id="abc-123"
    )
