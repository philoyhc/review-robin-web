"""Session Home's Owners card, a card of its own (19S Item 10).

A half-width card in the Danger Zone's column (above it since the
author's ruling of 2026-09-23), out of the Session details card and its
Lock / Unlock, always shown and in every lifecycle state. **Each action
saves at once** (author's ruling, 2026-09-23, retiring the staged Save /
Cancel): Add owner posts to ``owners/add`` and each row's Remove to
``owners/{user_id}/remove`` — plain forms, so the card works without
JavaScript. The last owner's Remove is disabled, your own row's asks
first, and removing yourself lands on the sessions lobby.
"""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services import session_owners

CREATOR = "alice@example.edu"


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


def _add_bob(db: Session, review_session: ReviewSession) -> User:
    bob = User(email="bob@example.edu", is_operator=True)
    db.add(bob)
    db.commit()
    alice = db.execute(select(User).where(User.email == CREATOR)).scalar_one()
    session_owners.add_owner(
        db, review_session=review_session, actor=alice, target=bob
    )
    return bob


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


def _home(client: TestClient, review_session: ReviewSession, query: str = "") -> str:
    return client.get(f"/operator/sessions/{review_session.id}{query}").text


def _tag(card: str, marker: str) -> str:
    """The opening tag of the element carrying ``marker``."""
    at = card.index(marker)
    return card[card.rfind("<", 0, at) : card.index(">", at) + 1]


def test_the_card_is_bounded_and_outside_the_details_card(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "OWN-CARD-1")
    body = _home(client, review_session)
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
    locked = _card(_home(client, review_session))
    editing = _card(_home(client, review_session, "?editing=1"))

    assert "data-edit-only" not in locked
    assert "data-display-only" not in locked
    assert "data-config-" not in locked
    assert locked == editing


def test_the_card_has_no_save_cancel_or_staging(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "OWN-CARD-3")
    body = _home(client, review_session)
    card = _card(body)

    for gone in (
        "data-owners-save",
        "data-owners-cancel",
        "data-owners-stager",
        "owners_original",
        "owners/save",
        "<noscript>",
    ):
        assert gone not in card, gone
    # The stager's own script, not merely its markers: the include is gone.
    assert "document.querySelectorAll('[data-owners-stager]')" not in body


def test_add_owner_is_a_form_to_owners_add(client: TestClient, db: Session) -> None:
    review_session = _create(client, db, "OWN-CARD-4")
    db.add(User(email="bob@example.edu", is_operator=True))
    db.commit()
    card = _card(_home(client, review_session))

    assert re.search(
        rf'<form method="post" id="owners-add-form"\s+'
        rf'action="/operator/sessions/{review_session.id}/owners/add">',
        card,
    )
    picker = _tag(card, 'id="owners-add-email"')
    assert 'name="target_email"' in picker and "required" in picker
    add = _tag(card, 'id="owners-add-submit"')
    assert 'class="btn secondary"' in add and 'type="submit"' in add
    assert "hidden" not in add


def test_add_owner_saves_at_once(client: TestClient, db: Session) -> None:
    review_session = _create(client, db, "OWN-CARD-5")
    db.add(User(email="bob@example.edu", is_operator=True))
    db.commit()

    response = client.post(
        f"/operator/sessions/{review_session.id}/owners/add",
        data={"target_email": "bob@example.edu"},
        follow_redirects=False,
    )

    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}#owners-card"
    )
    assert "bob@example.edu" in _card(_home(client, review_session))


def test_each_row_removes_at_once(client: TestClient, db: Session) -> None:
    review_session = _create(client, db, "OWN-CARD-6")
    bob = _add_bob(db, review_session)
    card = _card(_home(client, review_session))

    assert (
        f'action="/operator/sessions/{review_session.id}/owners/{bob.id}/remove"'
        in card
    )
    response = client.post(
        f"/operator/sessions/{review_session.id}/owners/{bob.id}/remove",
        follow_redirects=False,
    )
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}#owners-card"
    )
    card = _card(_home(client, review_session))
    table = card[card.index("<table>") : card.index("</table>")]
    assert "bob@example.edu" not in table
    # And he is a candidate again.
    assert 'value="bob@example.edu"' in card


def test_the_last_owners_remove_is_disabled(client: TestClient, db: Session) -> None:
    review_session = _create(client, db, "OWN-CARD-7")
    card = _card(_home(client, review_session))

    remove = re.search(r"<button class=\"chrome-link\" type=\"submit\"[^>]*>", card)
    assert remove and "disabled" in remove.group(0)


def test_removing_yourself_asks_first_and_lands_on_the_lobby(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "OWN-CARD-8")
    bob = _add_bob(db, review_session)
    alice = db.execute(select(User).where(User.email == CREATOR)).scalar_one()
    card = _card(_home(client, review_session))

    forms = re.findall(r"<form method=\"post\"[^>]*/remove\"[^>]*>", card)
    assert len(forms) == 2
    own = [f for f in forms if f"/owners/{alice.id}/remove" in f]
    other = [f for f in forms if f"/owners/{bob.id}/remove" in f]
    assert "window.confirm(" in own[0] and "data-owners-self-remove" in own[0]
    assert "window.confirm(" not in other[0]
    assert all("disabled" not in b for b in re.findall(r"<button[^>]*>Remove", card))

    response = client.post(
        f"/operator/sessions/{review_session.id}/owners/{alice.id}/remove",
        follow_redirects=False,
    )
    assert response.headers["location"] == "/operator/sessions"


def test_the_card_is_editable_on_an_activated_session(
    client: TestClient, db: Session
) -> None:
    """Every lifecycle state, as the lobby's tags (author's ruling)."""
    review_session = _create(client, db, "OWN-CARD-9")
    bob = _add_bob(db, review_session)
    review_session.status = "ready"
    db.commit()
    db.add(User(email="carol@example.edu", is_operator=True))
    db.commit()
    card = _card(_home(client, review_session))

    assert 'id="owners-add-form"' in card
    assert f"/owners/{bob.id}/remove" in card
    response = client.post(
        f"/operator/sessions/{review_session.id}/owners/add",
        data={"target_email": "carol@example.edu"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "carol@example.edu" in _card(_home(client, review_session))


def test_candidates_are_operators_not_already_owners(
    client: TestClient, db: Session
) -> None:
    """Add owner saves at once, so an existing owner would only be
    refused ``already_owner``."""
    review_session = _create(client, db, "OWN-CARD-10")
    _add_bob(db, review_session)
    db.add(User(email="carol@example.edu", is_operator=True))
    db.commit()
    card = _card(_home(client, review_session))
    datalist = card[card.index('<datalist id="owners-candidates">') :]
    datalist = datalist[: datalist.index("</datalist>")]

    assert 'value="carol@example.edu"' in datalist
    assert f'value="{CREATOR}"' not in datalist
    assert 'value="bob@example.edu"' not in datalist


def test_with_no_candidates_left_the_card_says_so(
    client: TestClient, db: Session
) -> None:
    """The creator is the workspace's only operator: nobody to add."""
    review_session = _create(client, db, "OWN-CARD-11")
    card = _card(_home(client, review_session))

    assert "Every workspace operator is already an owner." in card
    assert 'id="owners-add-form"' not in card
    assert "<datalist" not in card


def test_create_ships_its_add_owner_hidden_too(
    client: TestClient, db: Session, bob
) -> None:
    """Create's card still stages: the shared stager shows the button;
    without JavaScript it does nothing there."""
    db.add(User(email="bob@example.edu", is_operator=True))
    db.commit()
    body = client.get("/operator/sessions/new").text

    assert re.search(r'id="session-owners-add" data-owners-add hidden>', body)
