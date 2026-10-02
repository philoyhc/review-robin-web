"""B20 (2026-10-02): a scheduled trigger that raises never fails the page.

``observe_scheduled_events`` runs on Session Home's GET. Activation has
its own retry; invites and reminders do not yet (work in progress
awaiting Azure), so an uncaught render or write error used to propagate
and answer 500 on every load. Each trigger now runs guarded: rolled
back, logged, recorded once as ``session.scheduled_event_failed``.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession
from app.services import scheduled_events


def _make_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code, "description": "d"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _failed_rows(db: Session, review_session: ReviewSession) -> list[AuditEvent]:
    db.expire_all()
    return list(
        db.execute(
            select(AuditEvent)
            .where(
                AuditEvent.session_id == review_session.id,
                AuditEvent.event_type == scheduled_events.SCHEDULED_EVENT_FAILED,
            )
            .order_by(AuditEvent.id)
        ).scalars()
    )


def _boom(message: str):
    def _raise(*args, **kwargs):
        raise RuntimeError(message)

    return _raise


def _boom_with(exc: Exception):
    def _raise(*args, **kwargs):
        raise exc

    return _raise


def test_session_home_renders_when_a_trigger_raises(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    review_session = _make_session(client, db, "b20-home")
    monkeypatch.setattr(
        scheduled_events, "_observe_scheduled_invites", _boom("render failed")
    )

    response = client.get(f"/operator/sessions/{review_session.id}")

    assert response.status_code == 200
    rows = _failed_rows(db, review_session)
    assert len(rows) == 1
    assert rows[0].detail["context"] == {"trigger": "invites"}
    assert "render failed" in rows[0].detail["reason"]


def test_later_triggers_still_run_after_one_raises(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    review_session = _make_session(client, db, "b20-later")
    ran: list[str] = []
    monkeypatch.setattr(
        scheduled_events, "_observe_scheduled_invites", _boom("invites failed")
    )
    monkeypatch.setattr(
        scheduled_events,
        "_observe_scheduled_activation",
        lambda *a, **k: ran.append("activation"),
    )
    monkeypatch.setattr(
        scheduled_events,
        "_observe_scheduled_reminders",
        lambda *a, **k: ran.append("reminders"),
    )

    scheduled_events.observe_scheduled_events(db, review_session)

    assert ran == ["activation", "reminders"]


def test_a_repeated_failure_is_recorded_once(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    review_session = _make_session(client, db, "b20-repeat")
    monkeypatch.setattr(
        scheduled_events, "_observe_scheduled_reminders", _boom("write failed")
    )

    for _ in range(3):
        assert client.get(f"/operator/sessions/{review_session.id}").status_code == 200

    rows = _failed_rows(db, review_session)
    assert len(rows) == 1
    assert rows[0].detail["context"] == {"trigger": "reminders"}


def test_a_changed_failure_is_recorded_again(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    review_session = _make_session(client, db, "b20-changed")
    monkeypatch.setattr(
        scheduled_events, "_observe_scheduled_reminders", _boom("first")
    )
    scheduled_events.observe_scheduled_events(db, review_session)
    monkeypatch.setattr(
        scheduled_events, "_observe_scheduled_reminders", _boom("second")
    )
    scheduled_events.observe_scheduled_events(db, review_session)

    reasons = [row.detail["reason"] for row in _failed_rows(db, review_session)]
    assert len(reasons) == 2
    assert "first" in reasons[0] and "second" in reasons[1]


def test_two_failing_triggers_each_record_once(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    review_session = _make_session(client, db, "b20-two")
    monkeypatch.setattr(
        scheduled_events, "_observe_scheduled_invites", _boom("invites failed")
    )
    monkeypatch.setattr(
        scheduled_events, "_observe_scheduled_reminders", _boom("reminders failed")
    )

    for _ in range(3):
        assert client.get(f"/operator/sessions/{review_session.id}").status_code == 200

    triggers = [row.detail["context"]["trigger"] for row in _failed_rows(db, review_session)]
    assert sorted(triggers) == ["invites", "reminders"]


def test_an_audit_schema_error_still_propagates(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Strict-mode audit drift is the suite's gate; the guard must not
    swallow it."""
    review_session = _make_session(client, db, "b20-strict")
    monkeypatch.setattr(
        scheduled_events,
        "_observe_scheduled_invites",
        _boom_with(scheduled_events.audit.AuditDetailValidationError("x.y", None, "drift")),
    )

    with pytest.raises(scheduled_events.audit.AuditDetailValidationError):
        scheduled_events.observe_scheduled_events(db, review_session)


def test_a_failure_to_record_is_swallowed(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    review_session = _make_session(client, db, "b20-norecord")
    monkeypatch.setattr(
        scheduled_events, "_observe_scheduled_invites", _boom("render failed")
    )

    real_write = scheduled_events.audit.write_event

    def _failure_write_down(*args, **kwargs):
        if kwargs.get("event_type") == scheduled_events.SCHEDULED_EVENT_FAILED:
            raise RuntimeError("audit write failed")
        return real_write(*args, **kwargs)

    monkeypatch.setattr(scheduled_events.audit, "write_event", _failure_write_down)

    response = client.get(f"/operator/sessions/{review_session.id}")

    assert response.status_code == 200
    assert "Spring" in response.text
    assert _failed_rows(db, review_session) == []


def test_an_audit_schema_error_recording_the_failure_propagates(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    review_session = _make_session(client, db, "b20-strict-record")
    monkeypatch.setattr(
        scheduled_events, "_observe_scheduled_invites", _boom("render failed")
    )
    real_write = scheduled_events.audit.write_event

    def _drift(*args, **kwargs):
        if kwargs.get("event_type") == scheduled_events.SCHEDULED_EVENT_FAILED:
            raise scheduled_events.audit.AuditDetailValidationError(
                scheduled_events.SCHEDULED_EVENT_FAILED, None, "drift"
            )
        return real_write(*args, **kwargs)

    monkeypatch.setattr(scheduled_events.audit, "write_event", _drift)

    with pytest.raises(scheduled_events.audit.AuditDetailValidationError):
        scheduled_events.observe_scheduled_events(db, review_session)
