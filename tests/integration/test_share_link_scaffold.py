"""14F rung 3b: the Share the session link card, a scaffold.

The card sits on Invitations with real copy and layout; its link, its
two messages and its Copy buttons are inert until rung 3c. The Workflow
card's bulk-off line links to it.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings

from .test_invitations import _ready_session


def _card(body: str) -> str:
    return body.split('id="share-session-link"', 1)[1].split('id="invitations-table"', 1)[0]


def test_the_card_renders_on_invitations(client: TestClient, db: Session) -> None:
    session = _ready_session(client, db, code="share-scaffold")
    body = client.get(f"/operator/sessions/{session.public_id}/invitations").text
    card = _card(body)
    assert "Share the session link" in card
    assert 'data-share-message="invite"' in card
    assert 'data-share-message="reminder"' in card


def test_its_copy_buttons_are_inert(client: TestClient, db: Session) -> None:
    session = _ready_session(client, db, code="share-inert")
    card = _card(client.get(f"/operator/sessions/{session.public_id}/invitations").text)
    for button_id in (
        "share-session-link-copy",
        "share-invite-copy-subject",
        "share-invite-copy-body",
        "share-reminder-copy-subject",
        "share-reminder-copy-body",
    ):
        tag = card.split(f'id="{button_id}"', 1)[1].split(">", 1)[0]
        assert "disabled" in tag, button_id


def test_the_bulk_off_line_links_to_the_card(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "bulk_send", False)
    session = _ready_session(client, db, code="share-link-to")
    body = client.get(f"/operator/sessions/{session.public_id}/invitations").text
    line = body.split('id="next-action-bulk-off"', 1)[1].split("</p>", 1)[0]
    assert "/invitations#share-session-link" in line
