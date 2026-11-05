"""14F rung 1, the scaffold: copy and layout, nothing live.

- Session Home's Workflow card shows a placeholder due-action line once
  the operator has set invite or reminder offsets, and none before.
- The lobby has a Due pill slot that marks no session yet, and renders
  the pill for any session the view names.
- The email composer carries a "Send a test to me" button (wired in rung 2b).
"""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from app.web import views
from app.web.routes_operator import _lobby


def _client_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": f"Sess {code}", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(select(ReviewSession).where(ReviewSession.code == code)).scalar_one()


def test_session_home_shows_the_due_placeholder_only_with_offsets(
    client: TestClient, db: Session
) -> None:
    rs = _client_session(client, db, "DUE1")
    home = f"/operator/sessions/{rs.public_id}"
    assert "data-due-actions-placeholder" not in client.get(home).text
    rs.reminder_offsets = ["-2d"]
    db.commit()
    body = client.get(home).text
    assert "data-due-actions-placeholder" in body
    assert "Not live yet." in body


def test_the_lobby_marks_no_session_due_yet(client: TestClient, db: Session) -> None:
    _client_session(client, db, "DUE2")
    assert views.lobby_due_session_ids([]) == frozenset()
    assert "data-due-action" not in client.get("/operator/sessions").text


def test_the_lobby_renders_a_due_pill_for_a_named_session(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    rs = _client_session(client, db, "DUE3")
    monkeypatch.setattr(
        _lobby.views, "lobby_due_session_ids", lambda _sessions: frozenset({rs.public_id})
    )
    body = client.get("/operator/sessions").text
    row = body.split(f'data-session-id="{rs.public_id}"', 1)[1].split("</tr>", 1)[0]
    assert "data-due-action" in row
    assert ">Due</span>" in row


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
