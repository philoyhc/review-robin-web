"""Unit tests for ``app.services.extracts.audit_events_extract``
— Segment 12B PR 1.

Covers header shape, per-row contents (including JSON-encoded
``detail``), ordering, ActorEmail join, and the null /
naive-datetime edge cases.

The integration counterpart in
``tests/integration/test_extracts_audit_log_route.py`` covers
the HTTP route, audit emission, and Content-Disposition
headers.
"""

from __future__ import annotations

import datetime as dt
import json

from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession, User
from app.services.extracts.audit_events_extract import (
    HEADER,
    serialize_audit_events,
)


def _user(db: Session, *, email: str = "alice@example.edu") -> User:
    user = User(email=email, display_name=email.split("@", 1)[0])
    db.add(user)
    db.flush()
    return user


def _session(db: Session, *, code: str = "ae") -> ReviewSession:
    user = _user(db, email=f"op-{code}@example.edu")
    review_session = ReviewSession(
        name=code.title(), code=code, created_by_user_id=user.id
    )
    db.add(review_session)
    db.flush()
    return review_session


def _event(
    db: Session,
    review_session: ReviewSession,
    *,
    event_type: str = "test.event",
    severity: str = "info",
    summary: str = "test summary",
    actor: User | None = None,
    correlation_id: str | None = None,
    detail: dict | None = None,
    created_at: dt.datetime | None = None,
) -> AuditEvent:
    event = AuditEvent(
        session_id=review_session.id,
        actor_user_id=actor.id if actor is not None else None,
        event_type=event_type,
        severity=severity,
        summary=summary,
        detail=detail,
        correlation_id=correlation_id,
    )
    if created_at is not None:
        event.created_at = created_at
    db.add(event)
    db.flush()
    return event


def test_empty_session_emits_header_only(db: Session) -> None:
    review_session = _session(db, code="ae-empty")
    rows = list(serialize_audit_events(db, review_session))
    assert rows == [HEADER]


def test_per_row_shape_includes_all_columns(db: Session) -> None:
    review_session = _session(db, code="ae-shape")
    actor = _user(db, email="actor@example.edu")
    _event(
        db,
        review_session,
        event_type="reviewers.imported",
        severity="info",
        summary="Imported 3 reviewers",
        actor=actor,
        correlation_id="req-abc",
        detail={"counts": {"rows": 3}},
        created_at=dt.datetime(
            2026, 5, 10, 12, 0, 0, tzinfo=dt.timezone.utc
        ),
    )
    rows = list(serialize_audit_events(db, review_session))
    assert rows[0] == HEADER
    assert rows[1] == (
        "reviewers.imported",
        "info",
        "Imported 3 reviewers",
        "actor@example.edu",
        "req-abc",
        "2026-05-10T12:00:00+00:00",
        '{"counts":{"rows":3}}',
    )


def test_actor_email_blank_when_actor_is_null(db: Session) -> None:
    """System-emitted events (lifecycle, deadline observation)
    write with ``actor_user_id=None``. The ActorEmail cell
    collapses to empty rather than null."""

    review_session = _session(db, code="ae-noact")
    _event(
        db,
        review_session,
        event_type="deadline.observed",
        actor=None,
        detail=None,
    )
    rows = list(serialize_audit_events(db, review_session))
    assert rows[1][3] == ""  # ActorEmail
    assert rows[1][6] == ""  # DetailJson when detail is None


def test_detail_json_uses_sort_keys(db: Session) -> None:
    """``json.dumps(..., sort_keys=True)`` keeps re-exports
    byte-stable for the same logical content."""

    review_session = _session(db, code="ae-json")
    _event(
        db,
        review_session,
        event_type="x",
        detail={"z": 1, "a": 2, "m": 3},
    )
    rows = list(serialize_audit_events(db, review_session))
    assert rows[1][6] == '{"a":2,"m":3,"z":1}'


def test_ordering_is_created_at_then_id(db: Session) -> None:
    """Older events come first; ties on ``created_at`` break
    on ``id ASC``. Insertion order determines ``id`` so the
    test sets created_at explicitly."""

    review_session = _session(db, code="ae-order")
    base = dt.datetime(2026, 5, 10, 12, 0, 0, tzinfo=dt.timezone.utc)
    _event(
        db,
        review_session,
        event_type="b",
        summary="second",
        created_at=base + dt.timedelta(minutes=1),
    )
    _event(
        db,
        review_session,
        event_type="a",
        summary="first",
        created_at=base,
    )
    _event(
        db,
        review_session,
        event_type="c",
        summary="third",
        created_at=base + dt.timedelta(minutes=2),
    )
    rows = list(serialize_audit_events(db, review_session))
    summaries = [row[2] for row in rows[1:]]
    assert summaries == ["first", "second", "third"]


def test_naive_datetime_readback_normalises_to_utc(db: Session) -> None:
    """SQLite drops tzinfo on readback; the export forces UTC
    on naive datetimes so the cell shape is dialect-stable."""

    review_session = _session(db, code="ae-naive")
    naive = dt.datetime(2026, 5, 10, 12, 0, 0)  # no tzinfo
    _event(db, review_session, created_at=naive)
    rows = list(serialize_audit_events(db, review_session))
    # On SQLite the readback drops tzinfo; the helper restores UTC.
    assert rows[1][5].endswith("+00:00")


def test_correlation_id_optional(db: Session) -> None:
    """Some events (older ones / lifecycle observers) don't
    carry a correlation_id. Empty cell, not null."""

    review_session = _session(db, code="ae-corr")
    _event(db, review_session, correlation_id=None)
    rows = list(serialize_audit_events(db, review_session))
    assert rows[1][4] == ""


def test_session_id_filter_excludes_other_sessions(
    db: Session,
) -> None:
    """The extract filters by ``session_id`` so events on a
    sibling session don't bleed in."""

    a = _session(db, code="ae-a")
    b = _session(db, code="ae-b")
    _event(db, a, event_type="for-a")
    _event(db, b, event_type="for-b")
    rows_a = list(serialize_audit_events(db, a))
    rows_b = list(serialize_audit_events(db, b))
    assert [row[0] for row in rows_a[1:]] == ["for-a"]
    assert [row[0] for row in rows_b[1:]] == ["for-b"]


def test_detail_round_trips_through_json_parse(db: Session) -> None:
    """An analyst pulling the CSV should be able to
    ``json.loads`` the DetailJson cell back into the original
    envelope dict."""

    review_session = _session(db, code="ae-roundtrip")
    payload = {
        "session_id": review_session.id,
        "counts": {"rows": 17},
        "context": {"filename": "r.csv"},
    }
    _event(db, review_session, detail=payload)
    rows = list(serialize_audit_events(db, review_session))
    parsed = json.loads(rows[1][6])
    assert parsed == payload
