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


def test_activation_rechecks_that_it_is_due_under_the_lock(db: Session) -> None:
    """A Start moved later by a save after the page loaded does not
    fire early: due-ness is decided on the row under the lock."""
    session = _make_validated_session(db, "lock-activation-later")
    session.scheduled_activate_at = datetime(2099, 1, 1, 9, 0, tzinfo=timezone.utc)
    db.commit()
    _saved_behind_the_orm(
        db, session, "scheduled_activate_at", "2099-01-05 09:00:00.000000"
    )

    scheduled_events.observe_scheduled_events(
        db, session, now=datetime(2099, 1, 1, 10, 0, tzinfo=timezone.utc)
    )

    db.refresh(session)
    assert session.status == lifecycle.SessionStatus.validated.value
    assert session.scheduled_activate_at is not None


def test_lock_session_keeps_an_unflushed_edit(db: Session) -> None:
    """The app's sessions do not autoflush; re-reading under the lock
    must not discard an edit made before it."""
    session = _ready_session_with_invitations(db, "lock-unflushed")
    db.autoflush = False
    try:
        session.help_contact = "pending@x.edu"
        lock_session(db, session)
        assert session.help_contact == "pending@x.edu"
    finally:
        db.autoflush = True



def _commit_lands_at_the_lock(monkeypatch, db: Session, apply) -> None:
    """Patch ``scheduled_events.lock_session`` so another request's save
    (``apply``) lands just as the first lock is taken: a caller that
    locks before reading sees it, one that read first does not."""
    real = scheduled_events.lock_session
    fired: list[bool] = []

    def landing(db_, session_):
        if not fired:
            fired.append(True)
            apply(session_)
        return real(db_, session_)

    monkeypatch.setattr(scheduled_events, "lock_session", landing)


def test_the_session_home_save_locks_before_its_editability_gate(
    client, db: Session, monkeypatch
) -> None:
    """An activation landing as the save starts makes the session
    Activated; the save sees it and is refused rather than writing over
    a session that is no longer editable."""
    client.post(
        "/operator/sessions",
        data={"name": "Gate", "code": "lock-gate"},
        follow_redirects=False,
    )
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "lock-gate")
    ).scalar_one()
    _commit_lands_at_the_lock(
        monkeypatch,
        db,
        lambda s: _saved_behind_the_orm(db, s, "status", "ready"),
    )

    response = client.post(
        f"/operator/sessions/{session.id}/config",
        data={"name": "Renamed", "code": session.code, "display_timezone": "UTC"},
        follow_redirects=False,
    )

    assert response.status_code == 409
    db.expire_all()
    assert db.get(ReviewSession, session.id).name != "Renamed"


def test_the_lobby_save_locks_before_its_editability_gate(
    client, db: Session, monkeypatch
) -> None:
    client.post(
        "/operator/sessions",
        data={"name": "Lobby", "code": "lock-lobby"},
        follow_redirects=False,
    )
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "lock-lobby")
    ).scalar_one()
    _commit_lands_at_the_lock(
        monkeypatch,
        db,
        lambda s: _saved_behind_the_orm(db, s, "status", "ready"),
    )

    client.post(
        f"/operator/sessions/{session.id}/lobby-edit",
        data={"name": "Renamed", "code": session.code, "deadline": "", "tags": ""},
        follow_redirects=False,
    )

    db.expire_all()
    # Off ``is_editable`` the expander's Name is ignored.
    assert db.get(ReviewSession, session.id).name != "Renamed"


def test_the_settings_import_checks_under_the_lock(
    db: Session, monkeypatch
) -> None:
    """End moved earlier by a save landing as the import starts: the
    ordering check reads it and refuses a Start after the new End."""
    from app.services.session_config_io import Row, apply_session_config

    session = _make_validated_session(db, "lock-import")
    session.deadline = datetime(2026, 5, 15, 12, 0, tzinfo=timezone.utc)
    db.commit()
    _commit_lands_at_the_lock(
        monkeypatch,
        db,
        lambda s: _saved_behind_the_orm(
            db, s, "deadline", "2026-05-05 12:00:00.000000"
        ),
    )

    result = apply_session_config(
        db,
        session,
        [
            Row(
                "session.scheduled_activate_at",
                datetime(2026, 5, 10, 12, 0, tzinfo=timezone.utc).isoformat(),
                "datetime",
            )
        ],
    )

    assert [e.field for e in result.errors] == ["session.scheduled_activate_at"]


def test_the_settings_import_route_gates_editability_under_the_lock(
    client, db: Session, monkeypatch
) -> None:
    """A scheduled activation committing as the import starts: the
    route's editability gate reads it and refuses, rather than
    rebuilding a ready session's instruments."""
    client.post(
        "/operator/sessions",
        data={"name": "Import", "code": "lock-import-route"},
        follow_redirects=False,
    )
    session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "lock-import-route")
    ).scalar_one()
    _commit_lands_at_the_lock(
        monkeypatch,
        db,
        lambda s: _saved_behind_the_orm(db, s, "status", "ready"),
    )

    response = client.post(
        f"/operator/sessions/{session.id}/import-config",
        data={"confirm_replace": "true"},
        files={
            "file": (
                "settings.csv",
                b"field,value,data_type\nsession.name,Imported,string\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )

    assert "quick_setup_error" in response.headers["location"]
    assert _count(db, session, "session.settings_imported") == 0
