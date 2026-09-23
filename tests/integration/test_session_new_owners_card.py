"""19S Item 9 Part A rung 3 — the Owners card on Create, as a scaffold.

The card renders below the Tags card, the third card in the Create
page's right-hand ``.bottom-left`` column. The creator is always the
first owner; the box adds co-owners, comma-separated like the Tags box,
because there is no session yet to add them to one at a time.

**This rung is deliberately inert, and these tests pin inertness as a
property.** The input carries no ``name`` — so a browser does not submit
it — and no ``form=`` — which is what associates a control rendered
outside ``<form>`` with the create form. Both absences are asserted, and
a create carrying ``owners=`` naming a real workspace operator confirms
the route ignores it. Rung 4 inverts all three by design.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services import session_owners


def _card(body: str) -> str:
    """The Owners card's own markup — opening tag to its closing one.

    A ``<div>`` depth scan, as the Tags card's tests settled on: the
    Owners card is the page's last, which is exactly the case where
    bounding at the next sibling card silently returns the document's
    tail. ``test_the_card_helper_is_bounded`` guards it.
    """
    anchor = body.find('id="session-owners"')
    assert anchor != -1, "the Owners card is missing from the Create page"
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


def test_the_card_helper_is_bounded(client: TestClient) -> None:
    body = client.get("/operator/sessions/new").text
    card = _card(body)

    assert card.startswith('<div class="card" id="session-owners"')
    assert card.count("<div") == card.count("</div>")
    tail = body[body.index(card) + len(card):]
    assert "getElementById" in tail, "the page's scripts follow the card"
    assert "getElementById" not in card


def test_the_card_sits_below_tags_in_the_same_column(client: TestClient) -> None:
    body = client.get("/operator/sessions/new").text

    ui = body.find('id="user-interface-settings"')
    tags = body.find('id="session-tags"')
    owners = body.find('id="session-owners"')
    assert -1 not in (ui, tags, owners)
    assert ui < tags < owners

    # One .bottom-left column holds all three, so its gap spaces them.
    column = body.rfind('<div class="bottom-left">', 0, ui)
    assert column != -1
    assert body.rfind('<div class="bottom-left">', 0, owners) == column


def test_the_card_reads_like_the_tags_card_above_it(client: TestClient) -> None:
    """Heading as label, a ``.muted`` subtitle (``spec/ui_elements.md`` §8's
    one-field-card case), and no second "Owners" above the box."""
    card = _card(client.get("/operator/sessions/new").text)

    assert "Owners (optional)</h3>" in card
    assert '<p class="muted">' in card
    assert "comma-separated" in card
    assert "<label" not in card
    assert 'id="session-owners-heading"' in card
    assert 'aria-labelledby="session-owners-heading"' in card


def test_the_input_is_inert(client: TestClient) -> None:
    card = _card(client.get("/operator/sessions/new").text)

    assert 'id="owners"' in card, "the control is genuinely there"
    assert 'name="owners"' not in card
    assert "form=" not in card


def test_a_create_carrying_owners_adds_no_owner(
    client: TestClient, db: Session
) -> None:
    """The half no markup assertion can make. The named user is a real
    workspace operator, so ``add_owner`` would accept them — without that,
    "no co-owner" would pass for the wrong reason."""
    colleague = User(email="colleague@example.edu", is_operator=True)
    db.add(colleague)
    db.commit()

    response = client.post(
        "/operator/sessions",
        data={
            "name": "Owned",
            "code": "OWNERS-INERT",
            "description": "",
            "owners": "colleague@example.edu",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "OWNERS-INERT")
    ).scalar_one()
    owners = [row.email for row in session_owners.list_owners(db, review_session)]
    assert len(owners) == 1, owners
    assert "colleague@example.edu" not in owners
