"""Findings L4 (ruled 2026-10-17): the scheduled-event pass runs on the
operator GETs ``spec/lifecycle.md`` §8.3 names, not Session Home alone.

Session Home, the four Operations pages (Validate, Assignments,
Invitations, Responses) and the Sessions lobby each run
``scheduled_events.observe_scheduled_events`` before reading the
session, through ``observe_scheduled_events_on_load``, once per session
per request. The observable effect used here is the cheapest one: a
``draft`` session whose Start has passed is skipped and its schedule
cleared (``session.scheduled_activation_skipped``, §8.2.3).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession
from app.services import scheduled_events
from app.web.routes_operator import _shared


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


def _past_due_start(db: Session, review_session: ReviewSession) -> None:
    # Stored directly: the save-time lead-time floor refuses a past Start.
    review_session.scheduled_activate_at = datetime.now(timezone.utc) - timedelta(
        hours=1
    )
    db.commit()


def _skipped(db: Session, review_session: ReviewSession) -> list[AuditEvent]:
    db.expire_all()
    return list(
        db.execute(
            select(AuditEvent).where(
                AuditEvent.session_id == review_session.id,
                AuditEvent.event_type == "session.scheduled_activation_skipped",
            )
        ).scalars()
    )


_PAGES = {
    "home": "/operator/sessions/{id}",
    "validate": "/operator/sessions/{id}/validate",
    "assignments": "/operator/sessions/{id}/assignments",
    "invitations": "/operator/sessions/{id}/invitations",
    "responses": "/operator/sessions/{id}/responses",
    "lobby": "/operator/sessions",
}


@pytest.mark.parametrize("page", sorted(_PAGES))
def test_operator_get_fires_the_past_due_schedule(
    client: TestClient, db: Session, page: str
) -> None:
    path = _PAGES[page]
    review_session = _make_session(client, db, f"l4-{page}")
    _past_due_start(db, review_session)

    response = client.get(path.format(id=review_session.public_id))

    assert response.status_code == 200
    rows = _skipped(db, review_session)
    assert len(rows) == 1
    db.refresh(review_session)
    assert review_session.scheduled_activate_at is None


def test_lobby_runs_the_pass_for_every_listed_session(
    client: TestClient, db: Session
) -> None:
    first = _make_session(client, db, "l4-lobby-a")
    second = _make_session(client, db, "l4-lobby-b")
    _past_due_start(db, first)
    _past_due_start(db, second)

    assert client.get("/operator/sessions").status_code == 200

    assert len(_skipped(db, first)) == 1
    assert len(_skipped(db, second)) == 1


def test_lobby_skips_archived_and_expired_sessions(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The pass runs for the listed sessions that can still fire: not an
    archived one, which the table doesn't list, nor an expired one,
    whose past entries would cost a lock on every load."""
    listed = _make_session(client, db, "l4-arch-listed")
    archived = _make_session(client, db, "l4-arch-gone")
    archived.status = "archived"
    expired = _make_session(client, db, "l4-arch-expired")
    expired.status = "expired"
    db.commit()
    seen: list[int] = []
    monkeypatch.setattr(
        scheduled_events,
        "observe_scheduled_events",
        lambda db, session, **kwargs: seen.append(session.id),
    )

    assert client.get("/operator/sessions").status_code == 200

    assert listed.id in seen
    assert archived.id not in seen
    assert expired.id not in seen


def test_the_pass_runs_once_per_session_per_request(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[int] = []
    monkeypatch.setattr(
        scheduled_events,
        "observe_scheduled_events",
        lambda db, session, **kwargs: seen.append(session.id),
    )
    request = SimpleNamespace(state=SimpleNamespace(), url_for=None)
    a = SimpleNamespace(id=1)
    b = SimpleNamespace(id=2)

    _shared.observe_scheduled_events_on_load(request, db, [a])
    _shared.observe_scheduled_events_on_load(request, db, [a, b])

    assert seen == [1, 2]
