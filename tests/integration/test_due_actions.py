"""14F rung 5: the sends due by hand while scheduled email is off.

- An offset entry is due once its moment has passed, while someone is
  left to act on and it is not recorded on its anchor (`due_actions`).
- The Workflow card shows one line per due entry with its count, links
  to Invitations and the session link, and Mark as done.
- Mark as done records the entry as handled, which clears the line and
  is consumed on its anchor as a sent entry is, so 14G never sends it.
- With scheduled email on, nothing is due here: the observers send.
- The lobby's Due pill renders for any session the view names (rung 1).
- The composer's Send a test to me is wired (rung 2b).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditEvent, Invitation, ReviewSession
from app.services import due_actions, scheduled_events
from app.web import views
from app.web.routes_operator import _lobby

from .test_invitations import _ready_session


@pytest.fixture
def send_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "scheduled_send", False)


def _client_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": f"Sess {code}", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(select(ReviewSession).where(ReviewSession.code == code)).scalar_one()


def _invite_due(db: Session, rs: ReviewSession) -> None:
    rs.scheduled_activate_at = datetime.now(UTC) + timedelta(hours=1)
    rs.invite_offsets = ["-P1D", "-PT30M"]
    db.commit()


def test_an_invite_entry_is_due_once_its_moment_passes(
    client: TestClient, db: Session, send_off: None
) -> None:
    rs = _ready_session(client, db, code="due-inv")
    _invite_due(db, rs)
    [action] = due_actions.due_actions(db, rs)
    assert (action.kind, action.offset_index, action.offset, action.count) == (
        "invite",
        0,
        "-P1D",
        1,
    )


def test_nothing_is_due_with_no_one_left_or_with_sending_on(
    client: TestClient, db: Session, send_off: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    rs = _ready_session(client, db, code="due-none")
    _invite_due(db, rs)
    monkeypatch.setattr(settings, "scheduled_send", True)
    assert due_actions.due_actions(db, rs) == []
    monkeypatch.setattr(settings, "scheduled_send", False)
    invitation = db.execute(select(Invitation).where(Invitation.session_id == rs.id)).scalar_one()
    client.post(f"/operator/sessions/{rs.public_id}/invitations/{invitation.id}/send")
    assert due_actions.due_actions(db, rs) == []  # nobody left to invite


def test_a_reminder_is_due_while_a_reviewer_is_unfinished(
    client: TestClient, db: Session, send_off: None
) -> None:
    rs = _ready_session(client, db, code="due-rem")
    invitation = db.execute(select(Invitation).where(Invitation.session_id == rs.id)).scalar_one()
    client.post(f"/operator/sessions/{rs.public_id}/invitations/{invitation.id}/send")
    rs.deadline = datetime.now(UTC) + timedelta(hours=1)
    rs.reminder_offsets = ["-P1D"]
    db.commit()
    [action] = due_actions.due_actions(db, rs)
    assert (action.kind, action.count) == ("reminder", 1)


def test_the_card_shows_the_line_and_mark_as_done_clears_it(
    client: TestClient, db: Session, send_off: None
) -> None:
    rs = _ready_session(client, db, code="due-card")
    _invite_due(db, rs)
    home = f"/operator/sessions/{rs.public_id}"
    body = client.get(home).text
    line = body.split('data-due-prompt="invite-0"', 1)[1].split("</div>", 1)[0]
    assert "Invitations due (-P1D from Start," in line
    assert "1 not yet sent." in line
    assert "#share-session-link" in line
    assert "Mark as done" in line

    response = client.post(
        f"{home}/workflow/due-done",
        data={"kind": "invite", "offset_index": "0"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert 'data-due-prompt="invite-0"' not in client.get(home).text
    [event] = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "session.scheduled_invites_handled")
    ).scalars()
    assert event.detail is not None
    assert event.detail["context"]["offset"] == "-P1D"
    # Consumed on its anchor as a sent entry is: 14G will not send it.
    assert scheduled_events.fired_offsets(db, rs, "invite", rs.scheduled_activate_at) == {0: "-P1D"}


def test_a_reminders_mark_as_done_is_recorded_and_consumed(
    client: TestClient, db: Session, send_off: None
) -> None:
    rs = _ready_session(client, db, code="due-rem-done")
    invitation = db.execute(select(Invitation).where(Invitation.session_id == rs.id)).scalar_one()
    client.post(f"/operator/sessions/{rs.public_id}/invitations/{invitation.id}/send")
    rs.deadline = datetime.now(UTC) + timedelta(hours=1)
    rs.reminder_offsets = ["-P1D"]
    db.commit()
    response = client.post(
        f"/operator/sessions/{rs.public_id}/workflow/due-done",
        data={"kind": "reminder", "offset_index": "0"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert due_actions.due_actions(db, rs) == []
    assert scheduled_events.fired_offsets(db, rs, "reminder", rs.deadline) == {0: "-P1D"}
    # A new End is a new anchor: the entry prompts again there.
    rs.deadline = datetime.now(UTC) + timedelta(hours=2)
    db.commit()
    assert [a.kind for a in due_actions.due_actions(db, rs)] == ["reminder"]


def test_an_unknown_kind_is_not_due(client: TestClient, db: Session, send_off: None) -> None:
    rs = _ready_session(client, db, code="due-kind")
    _invite_due(db, rs)
    response = client.post(
        f"/operator/sessions/{rs.public_id}/workflow/due-done",
        data={"kind": "observer", "offset_index": "0"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert len(due_actions.due_actions(db, rs)) == 1


def test_mark_as_done_on_an_entry_not_due_changes_nothing(
    client: TestClient, db: Session, send_off: None
) -> None:
    rs = _ready_session(client, db, code="due-stale")
    _invite_due(db, rs)
    response = client.post(
        f"/operator/sessions/{rs.public_id}/workflow/due-done",
        data={"kind": "invite", "offset_index": "1"},  # not yet due
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert (
        db.execute(
            select(AuditEvent).where(AuditEvent.event_type == "session.scheduled_invites_handled")
        ).first()
        is None
    )


def test_the_lobby_renders_a_due_pill_for_a_named_session(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    rs = _client_session(client, db, "DUE3")
    monkeypatch.setattr(
        _lobby.views, "lobby_due_session_ids", lambda _db, _sessions: frozenset({rs.public_id})
    )
    body = client.get("/operator/sessions").text
    row = body.split(f'data-session-id="{rs.public_id}"', 1)[1].split("</tr>", 1)[0]
    assert "data-due-action" in row
    assert ">Due</span>" in row


def test_the_lobby_marks_a_session_with_a_prompt_due(
    client: TestClient, db: Session, send_off: None
) -> None:
    due = _ready_session(client, db, code="due-lobby")
    calm = _client_session(client, db, "calm-lobby")
    assert views.lobby_due_session_ids(db, [due, calm]) == frozenset()
    _invite_due(db, due)
    assert views.lobby_due_session_ids(db, [due, calm]) == {due.public_id}
    body = client.get("/operator/sessions").text
    row = body.split(f'data-session-id="{due.public_id}"', 1)[1].split("</tr>", 1)[0]
    assert ">Due</span>" in row


def test_the_lobby_marks_a_scheduled_start_that_gave_up(client: TestClient, db: Session) -> None:
    from app.services import audit

    rs = _client_session(client, db, "gave-up")
    audit.write_event(
        db,
        event_type=due_actions.ACTIVATION_GAVE_UP,
        summary="gave up",
        actor_user_id=None,
        session=rs,
        reason="lifecycle_error",
        context={"scheduled_at": datetime.now(UTC).isoformat(), "attempts": 3},
    )
    db.commit()
    assert views.lobby_due_session_ids(db, [rs]) == {rs.public_id}
    # Anything since — here an edit — clears it, as on the card.
    client.post(
        f"/operator/sessions/{rs.public_id}/config",
        data={"name": "Renamed", "code": rs.code},
        follow_redirects=False,
    )
    assert views.lobby_due_session_ids(db, [rs]) == frozenset()


def test_the_composer_send_a_test_button_posts_the_form_to_its_own_action(
    client: TestClient, db: Session
) -> None:
    """Rung 1 placed it inert; rung 2b wired it (`test_email_test_send.py`)."""
    rs = _client_session(client, db, "DUE4")
    body = client.get(f"/operator/sessions/{rs.public_id}/setup-invite").text
    match = re.search(r'<button[^>]*id="setupinvite-send-test"[^>]*>[^<]*</button>', body)
    assert match is not None
    button = match.group(0)
    assert " disabled" not in button
    assert 'form="setupinvite-form"' in button
    assert "/setup-invite/send-test" in button
    assert "Send a test to me" in button
