"""19S Item 9 Part A rung 3 — the Owners card on Create, as a scaffold.

The card renders below the Tags card, the third card in the Create
page's right-hand ``.bottom-left`` column, with **the same UX as Session
Home's Owners card** (author's ruling, 2026-09-23): the owners table,
then a one-at-a-time Add-owner picker suggesting workspace operators.
The creator is the first owner, listed without a Remove action, and is
not offered as a candidate.

**This rung is deliberately inert, and these tests pin inertness as a
property.** The email input carries no ``name`` and no ``form=``, and
Add owner is a plain ``type="button"`` with nothing behind it; a create
carrying ``owners=`` naming a real workspace operator confirms the route
ignores it. Rung 4 stages rows and wires the write.
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


def _operator(db: Session, email: str, *, is_operator: bool = True) -> User:
    user = User(email=email, is_operator=is_operator)
    db.add(user)
    db.commit()
    return user


def test_the_card_mirrors_session_home(client: TestClient, db: Session) -> None:
    """Session Home's shape: heading, subtitle, the owners table with the
    same columns, the picker's own label, and Add owner. Like Session
    Home, the picker renders only when there is someone to add."""
    _operator(db, "colleague@example.edu")
    card = _card(client.get("/operator/sessions/new").text)

    assert "Owners (optional)</h3>" in card
    assert '<p class="muted">' in card
    for column in ("Email", "Name", "Role", "Added", "Action"):
        assert f">{column}</th>" in card, column
    assert "Pick or search for a workspace operator:" in card
    assert ">Add owner</button>" in card


def test_the_creator_is_the_first_owner_and_cannot_be_removed(
    client: TestClient, db: Session
) -> None:
    body = client.get("/operator/sessions/new").text
    card = _card(body)
    creator = db.execute(select(User)).scalars().first()

    assert f"<code>{creator.email}</code>" in card
    assert "<td>owner</td>" in card
    assert "Remove" not in card, "a session always keeps one owner"


def test_the_picker_suggests_other_workspace_operators(
    client: TestClient, db: Session
) -> None:
    """Everyone ``add_owner`` would accept, minus the creator — who owns
    the session the moment it exists. A non-operator is never offered."""
    _operator(db, "colleague@example.edu")
    _operator(db, "outsider@example.edu", is_operator=False)
    card = _card(client.get("/operator/sessions/new").text)
    creator = db.execute(
        select(User).where(User.email != "colleague@example.edu")
        .where(User.email != "outsider@example.edu")
    ).scalars().first()

    datalist = card[card.index("<datalist"):card.index("</datalist>")]
    assert 'value="colleague@example.edu"' in datalist
    assert "outsider@example.edu" not in datalist
    assert f'value="{creator.email}"' not in datalist
    assert 'list="session-owners-candidates"' in card


def test_with_no_one_to_add_the_picker_says_so(client: TestClient) -> None:
    card = _card(client.get("/operator/sessions/new").text)

    assert "No other workspace operators are available to add." in card
    assert "<datalist" not in card


def test_the_picker_is_inert(client: TestClient, db: Session) -> None:
    """Both halves of inertness, asserted as absences, plus a button that
    submits nothing. Rung 4 inverts them."""
    _operator(db, "colleague@example.edu")
    card = _card(client.get("/operator/sessions/new").text)

    assert 'id="session-owners-email"' in card, "the control is there"
    assert 'name="owners"' not in card
    assert "form=" not in card
    assert 'type="button"' in card and 'type="submit"' not in card


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
