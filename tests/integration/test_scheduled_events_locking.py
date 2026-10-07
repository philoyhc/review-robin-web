"""Findings Bc3 (ruled 2026-10-07): the scheduled-event observers decide
and record each entry under a session lock that re-reads the row.

SQLite has one writer, so the lock itself cannot contend here; these
tests pin what it is for. A raw ``UPDATE`` stands in for another
request's committed save: it changes the row behind the ORM's back, so
the session object still holds the values loaded before it, as an
observer's would."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, EmailOutbox, ReviewSession
from app.services import invitations as invitations_service
from app.services import scheduled_events
from app.services import session_lifecycle as lifecycle
from app.services.scheduled_events import lock_session

from .test_scheduled_activation import _make_validated_session
from .test_scheduled_reminders import (
    _ready_session_with_invitations,
    _stub_build_url,
)


def _saved_behind_the_orm(
    db: Session, session: ReviewSession, column: str, value: object
) -> None:
    db.execute(
        text(f"UPDATE sessions SET {column} = :value WHERE id = :id"),
        {
            "value": json.dumps(value) if isinstance(value, list) else value,
            "id": session.id,
        },
    )


def _count(db: Session, session: ReviewSession, event_type: str) -> int:
    return len(
        db.execute(
            select(AuditEvent.id).where(
                AuditEvent.session_id == session.id,
                AuditEvent.event_type == event_type,
            )
        ).all()
    )


def _reminder_rows(db: Session, session: ReviewSession) -> list[EmailOutbox]:
    return [
        row
        for row in db.execute(
            select(EmailOutbox).where(EmailOutbox.session_id == session.id)
        ).scalars()
        if (row.correlation_id or "").startswith("reminder:")
    ]


def test_lock_session_rereads_the_row(db: Session) -> None:
    session = _ready_session_with_invitations(db, "lock-reread")
    session.reminder_offsets = ["-PT8H"]
    db.commit()
    _saved_behind_the_orm(db, session, "reminder_offsets", ["-PT1H"])
    assert session.reminder_offsets == ["-PT8H"]

    locked = lock_session(db, session)

    assert locked is session
    assert session.reminder_offsets == ["-PT1H"]


def test_the_observer_fires_from_the_lists_saved_after_it_loaded(
    db: Session,
) -> None:
    """The page loaded ``-PT8H`` (due); a save then made it ``-PT1H``
    (three hours out). The pass decides under the lock, on the saved
    list, and sends nothing."""
    session = _ready_session_with_invitations(db, "lock-saved-first")
    session.deadline = datetime.now(timezone.utc) + timedelta(hours=4)
    session.reminder_offsets = ["-PT8H"]
    db.commit()
    _saved_behind_the_orm(db, session, "reminder_offsets", ["-PT1H"])

    scheduled_events.observe_scheduled_events(
        db, session, build_invite_url=_stub_build_url
    )

    assert _count(db, session, "session.scheduled_reminders_fired") == 0
    assert _reminder_rows(db, session) == []


def test_activation_rereads_its_anchor(db: Session) -> None:
    """A Start cleared by a save after the page loaded does not fire:
    the idempotency check reads the row under the lock."""
    session = _make_validated_session(db, "lock-activation")
    session.scheduled_activate_at = datetime(2099, 1, 1, 9, 0, tzinfo=timezone.utc)
    db.commit()
    _saved_behind_the_orm(db, session, "scheduled_activate_at", None)

    scheduled_events.observe_scheduled_events(
        db, session, now=datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc)
    )

    db.refresh(session)
    assert session.status == lifecycle.SessionStatus.validated.value
    assert _count(db, session, "session.activated") == 0


def test_an_entry_is_sent_and_recorded_in_one_transaction(
    db: Session, monkeypatch
) -> None:
    """A failure part-way through an entry's sends rolls the whole
    entry back, the sends already made included, so the record and the
    outbox never disagree; the next pass sends it whole."""
    session = _ready_session_with_invitations(
        db, "lock-atomic", reviewer_count=2
    )
    session.deadline = datetime.now(timezone.utc) + timedelta(hours=4)
    session.reminder_offsets = ["-PT8H"]
    db.commit()

    real = invitations_service.send_reminder
    calls: list[int] = []

    def fail_on_second(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("transport down")
        return real(*args, **kwargs)

    monkeypatch.setattr(invitations_service, "send_reminder", fail_on_second)
    scheduled_events.observe_scheduled_events(
        db, session, build_invite_url=_stub_build_url
    )
    assert _reminder_rows(db, session) == []
    assert _count(db, session, "session.scheduled_reminders_fired") == 0

    monkeypatch.setattr(invitations_service, "send_reminder", real)
    scheduled_events.observe_scheduled_events(
        db, session, build_invite_url=_stub_build_url
    )
    assert len(_reminder_rows(db, session)) == 2
    assert _count(db, session, "session.scheduled_reminders_fired") == 1


def test_the_save_check_takes_the_same_lock(db: Session, monkeypatch) -> None:
    from app.services.scheduled_events import _fired, fired_offset_errors

    session = _ready_session_with_invitations(db, "lock-save-check")
    locked: list[int] = []
    real = _fired.lock_session

    def spy(db_, session_):
        locked.append(session_.id)
        return real(db_, session_)

    monkeypatch.setattr(_fired, "lock_session", spy)
    fired_offset_errors(
        db,
        session,
        scheduled_activate_at=None,
        invite_offsets=[],
        deadline=None,
        reminder_offsets=[],
    )
    assert locked == [session.id]
