"""14F rungs 3b–3c: the Share the session link card on Invitations.

The card shows the session's stable link, absolute, and the session's
invitation and reminder templates written for everyone: that link as
``$invite_url`` and no reviewer. Its boxes are editable and unsaved, and
each Copy button names the box it copies. The Workflow card's bulk-off
line links to it.
"""

from __future__ import annotations

import html

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ReviewSession
from app.services import email_templates

from .test_invitations import _ready_session


def _card(body: str) -> str:
    return body.split('id="share-session-link"', 1)[1].split('id="invitations-table"', 1)[0]


def _page(client: TestClient, session: ReviewSession) -> str:
    return client.get(f"/operator/sessions/{session.public_id}/invitations").text


def _value(card: str, element_id: str) -> str:
    tag = card.split(f'id="{element_id}"', 1)[1]
    if tag.lstrip().startswith("rows"):
        return html.unescape(tag.split(">", 1)[1].split("</textarea>", 1)[0])
    return html.unescape(tag.split('value="', 1)[1].split('"', 1)[0])


def test_the_link_is_the_sessions_stable_link_absolute(client: TestClient, db: Session) -> None:
    session = _ready_session(client, db, code="share-link")
    link = _value(_card(_page(client, session)), "share-session-link-url")
    assert link.startswith("http")
    assert link.endswith(f"/me/sessions/{session.public_id}")


def test_the_messages_carry_the_link_and_no_name(client: TestClient, db: Session) -> None:
    session = _ready_session(client, db, code="share-msgs")
    card = _card(_page(client, session))
    link = _value(card, "share-session-link-url")
    for key in ("invite", "reminder"):
        body = _value(card, f"share-{key}-body")
        assert link in body, key
        assert "Hi ," not in body and "Hi\n" not in body, key
        assert session.name in _value(card, f"share-{key}-subject"), key


def test_an_override_renders_as_written(client: TestClient, db: Session) -> None:
    session = _ready_session(client, db, code="share-override")
    email_templates.set_overrides(session, {"reminder_body": "Nudge: $invite_url"})
    db.commit()
    card = _card(_page(client, session))
    link = _value(card, "share-session-link-url")
    assert _value(card, "share-reminder-body").strip() == f"Nudge: {link}"


def test_every_copy_button_is_live_and_names_its_box(client: TestClient, db: Session) -> None:
    session = _ready_session(client, db, code="share-copy")
    card = _card(_page(client, session))
    for button_id, source in (
        ("share-session-link-copy", "share-session-link-url"),
        ("share-invite-copy-subject", "share-invite-subject"),
        ("share-invite-copy-body", "share-invite-body"),
        ("share-reminder-copy-subject", "share-reminder-subject"),
        ("share-reminder-copy-body", "share-reminder-body"),
    ):
        tag = card.split(f'id="{button_id}"', 1)[1].split(">", 1)[0]
        assert "disabled" not in tag, button_id
        assert f'data-copy-from="{source}"' in tag, button_id
    assert 'id="share-copy-status"' in card


def test_the_bulk_off_line_links_to_the_card(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "bulk_send", False)
    session = _ready_session(client, db, code="share-link-to")
    line = _page(client, session).split('id="next-action-bulk-off"', 1)[1].split("</p>", 1)[0]
    assert "/invitations#share-session-link" in line
