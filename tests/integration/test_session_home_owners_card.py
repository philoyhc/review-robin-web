"""Session Home's Owners card, a card of its own (19S Item 10 rung B).

The scaffold: the card leaves the Session details card and its Lock /
Unlock for a half-width card below the Danger Zone, always shown and in
every lifecycle state (author's ruling, 2026-09-23). Its **Save** and
**Cancel** are present and inert until rungs C–D wire the card's own
save; meanwhile Add owner and each row's Remove keep their own forms.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User


def _create(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Owned", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _card(body: str) -> str:
    """The Owners card's markup, opening tag to its closing one, by a
    ``<div>`` depth scan (the Tags card test's helper)."""
    anchor = body.find('id="owners-card"')
    assert anchor != -1, "the Owners card is missing from Session Home"
    start = body.rfind("<div", 0, anchor)
    depth = 0
    i = start
    while True:
        opened = body.find("<div", i)
        closed = body.find("</div>", i)
        assert closed != -1, "the Owners card's <div> is never closed"
        if opened != -1 and opened < closed:
            depth += 1
            i = opened + len("<div")
            continue
        depth -= 1
        i = closed + len("</div>")
        if depth == 0:
            return body[start:i]


def test_the_card_is_bounded_and_outside_the_details_card(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "OWN-CARD-1")
    body = client.get(f"/operator/sessions/{review_session.id}").text
    card = _card(body)

    assert card.startswith('<div class="card" id="owners-card"')
    assert card.count("<div") == card.count("</div>")
    config = body.find('id="session-config"')
    assert body.find("window.sessionConfig", config) < body.index(card), (
        "the Owners card follows the details card and is not inside it"
    )
    assert "<h2>Owners</h2>" in card


def test_the_card_does_not_swap_with_the_details_card(
    client: TestClient, db: Session
) -> None:
    """No display / edit halves: the card is the same locked or not."""
    review_session = _create(client, db, "OWN-CARD-2")
    locked = _card(client.get(f"/operator/sessions/{review_session.id}").text)
    editing = _card(
        client.get(f"/operator/sessions/{review_session.id}?editing=1").text
    )

    assert "data-edit-only" not in locked
    assert "data-display-only" not in locked
    assert "data-config-" not in locked
    assert locked == editing
    assert 'type="submit">Remove</button>' in locked


def test_the_card_is_editable_on_an_activated_session(
    client: TestClient, db: Session
) -> None:
    """Every lifecycle state, as the lobby's tags (author's ruling)."""
    review_session = _create(client, db, "OWN-CARD-3")
    review_session.status = "ready"
    db.commit()
    card = _card(client.get(f"/operator/sessions/{review_session.id}").text)

    assert "/owners/" in card and "/remove" in card
    assert 'type="submit">Remove</button>' in card


def test_save_and_cancel_are_present_and_inert(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "OWN-CARD-4")
    card = _card(client.get(f"/operator/sessions/{review_session.id}").text)

    for marker, label in (
        ("data-owners-save", "Save"),
        ("data-owners-cancel", "Cancel"),
    ):
        start = card.index(marker)
        tag = card[card.rfind("<button", 0, start) : card.index(">", start) + 1]
        assert 'type="button"' in tag, f"{label} must not submit anything yet"
        assert "disabled" in tag
        assert 'class="btn secondary"' in tag
        assert f">{label}</button>" in card[start:]


def test_add_owner_is_secondary(client: TestClient, db: Session) -> None:
    """With a candidate to add, the picker's button is Secondary, as on
    Create: the Workflow card holds the page's one Primary."""
    review_session = _create(client, db, "OWN-CARD-5")
    db.add(User(email="bob@example.edu", is_operator=True))
    db.commit()
    card = _card(client.get(f"/operator/sessions/{review_session.id}").text)

    assert '<button class="btn secondary" type="submit"\n' in card
    assert 'id="owners-add-submit">Add owner</button>' in card
