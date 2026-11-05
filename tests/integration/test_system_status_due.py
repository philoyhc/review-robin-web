"""System Status's Due next card (segment 22G Item 1): what the clock
does next across the workspace, read from the columns its pick reads."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession
from app.services import session_lifecycle as lifecycle
from app.services import system_status

from .test_scheduled_activation import _make_validated_session

NOW = datetime(2026, 11, 5, 2, 0, tzinfo=UTC)


def _session(db: Session, code: str, **fields: object) -> ReviewSession:
    rs = _make_validated_session(db, code)
    for name, value in fields.items():
        setattr(rs, name, value)
    db.commit()
    return rs


def test_nothing_scheduled(db: Session) -> None:
    due = system_status.due_next(db, now=NOW)
    assert due.next_start is None
    assert due.next_close is None
    assert due.next_release_stamp is None
    assert due.due_now == []
    assert due.failed_activations == []


def test_the_earliest_start_to_come(db: Session) -> None:
    _session(db, "due-later", scheduled_activate_at=NOW + timedelta(days=2))
    soon = _session(db, "due-soon", scheduled_activate_at=NOW + timedelta(hours=3))
    _session(
        db,
        "due-archived",
        scheduled_activate_at=NOW + timedelta(hours=1),
        status=lifecycle.SessionStatus.archived.value,
    )
    due = system_status.due_next(db, now=NOW)
    assert due.next_start is not None
    assert due.next_start.session_id == soon.id
    assert due.next_start.at == NOW + timedelta(hours=3)


def test_an_open_session_closes_at_end_or_with_no_end_at_release(db: Session) -> None:
    ready = lifecycle.SessionStatus.ready.value
    _session(db, "due-end", status=ready, deadline=NOW + timedelta(days=1))
    by_release = _session(
        db, "due-release-close", status=ready, responses_release_at=NOW + timedelta(hours=5)
    )
    # A draft with an End is not open, so it does not close.
    _session(db, "due-draft-end", deadline=NOW + timedelta(hours=1))
    due = system_status.due_next(db, now=NOW)
    assert due.next_close is not None
    assert due.next_close.session_id == by_release.id
    assert due.next_close.at == NOW + timedelta(hours=5)


def test_the_next_release_stamp_is_either_end_of_the_window(db: Session) -> None:
    expired = lifecycle.SessionStatus.expired.value
    _session(
        db,
        "due-window",
        status=expired,
        responses_release_at=NOW - timedelta(days=1),
        responses_release_until=NOW + timedelta(hours=7),
    )
    opening = _session(
        db, "due-opening", status=expired, responses_release_at=NOW + timedelta(hours=2)
    )
    due = system_status.due_next(db, now=NOW)
    assert due.next_release_stamp is not None
    assert due.next_release_stamp.session_id == opening.id


def test_due_now_is_what_the_clock_would_pick(db: Session) -> None:
    passed = _session(db, "due-passed", scheduled_activate_at=NOW - timedelta(minutes=5))
    due = system_status.due_next(db, now=NOW)
    assert [s.session_id for s in due.due_now] == [passed.id]


def test_failed_activations_within_seven_days_newest_first(db: Session) -> None:
    rs = _session(db, "due-failed")
    for age in (timedelta(days=8), timedelta(days=3), timedelta(hours=1)):
        db.add(
            AuditEvent(
                session_id=rs.id,
                event_type=system_status.ACTIVATION_FAILED_PERSISTENT,
                summary="Scheduled activation failed",
                created_at=NOW - age,
            )
        )
    db.commit()
    due = system_status.due_next(db, now=NOW)
    assert [s.at for s in due.failed_activations] == [
        NOW - timedelta(hours=1),
        NOW - timedelta(days=3),
    ]
    assert all(s.session_id == rs.id for s in due.failed_activations)
