"""14F rungs 3b–3c: the Share the session link card on Invitations.

The card shows the session's stable link, absolute, with a Copy link
button. The Workflow card's bulk-off line links to it.
"""

from __future__ import annotations

import html

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import ReviewSession

from .test_invitations import _ready_session


def _card(body: str) -> str:
    return body.split('id="share-session-link"', 1)[1].split('id="invitations-table"', 1)[0]


def _page(client: TestClient, session: ReviewSession) -> str:
    return client.get(f"/operator/sessions/{session.public_id}/invitations").text


def _value(card: str, element_id: str) -> str:
    tag = card.split(f'id="{element_id}"', 1)[1]
    return html.unescape(tag.split('value="', 1)[1].split('"', 1)[0])


def test_the_link_is_the_sessions_stable_link_absolute(client: TestClient, db: Session) -> None:
    session = _ready_session(client, db, code="share-link")
    link = _value(_card(_page(client, session)), "share-session-link-url")
    assert link.startswith("http")
    assert link.endswith(f"/me/sessions/{session.public_id}")


def test_the_card_is_the_link_alone(client: TestClient, db: Session) -> None:
    """The author cut the card to its title, help text, link and Copy
    link (2026-11-05): no message boxes."""
    session = _ready_session(client, db, code="share-alone")
    card = _card(_page(client, session))
    assert "Only eligible signed in participants will be able to reach the" in card
    assert "only when the session is open to" in card
    assert "<textarea" not in card
    assert "data-share-message" not in card
    tag = card.split('id="share-session-link-copy"', 1)[1].split(">", 1)[0]
    assert "disabled" not in tag
    assert 'data-copy-from="share-session-link-url"' in tag
    assert 'id="share-copy-status"' in card


def test_the_bulk_off_line_links_to_the_card(client: TestClient, db: Session) -> None:
    # Bulk is off whatever ``RRW_BULK_SEND`` says until 14G (findings L2).
    session = _ready_session(client, db, code="share-link-to")
    line = _page(client, session).split('id="next-action-bulk-off"', 1)[1].split("</p>", 1)[0]
    assert "/invitations#share-session-link" in line
