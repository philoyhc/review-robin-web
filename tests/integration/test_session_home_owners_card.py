"""Session Home's Owners card, a card of its own (19S Item 10).

Rung B moved the card out of the Session details card and its Lock /
Unlock to a half-width card below the Danger Zone, always shown and in
every lifecycle state (author's ruling, 2026-09-23). Rung D makes it
stage as Create's does and save with its own **Save**:

- the table is ``_owners_stager_js``'s — Add owner and Remove change the
  table only, and each row carries a hidden ``owners`` input bound to
  the card's own form, which posts to ``POST /sessions/{id}/owners``
  beside ``owners_original``, the set rendered here;
- **Save** and **Cancel** wake once the table or the picker changes;
  Cancel is the form's reset, which the stager answers by rebuilding
  the rows;
- **without JavaScript** the staging buttons stay ``hidden``, the picker
  posts its one address with Save, and a ``<noscript>`` Remove per row
  posts to the old route — left off the last owner and your own row.

What the script does (the last-owner disable, the self-removal confirm,
Cancel restoring the rows, Save waking) was driven in Chromium with
JavaScript on and off; the suite runs no browser, so this file pins the
markup those behaviors hang on.
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


def test_the_card_is_a_stager_bound_to_its_own_form(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "OWN-CARD-3")
    card = _card(_home(client, review_session))
    form_id = f"owners-save-{review_session.id}"
    bound = f'form="{form_id}"'

    assert "data-owners-stager" in _tag(card, 'id="owners-card"')
    assert f'data-owners-form="{form_id}"' in card
    assert f'data-owners-self="{CREATOR}"' in card, (
        "the stager knows whose row asks before removing"
    )
    assert re.search(
        rf'<form id="{form_id}" method="post"\s+'
        rf'action="/operator/sessions/{review_session.id}/owners">',
        card,
    )
    # Each row's owner, bound to the card's form: the rows are the set.
    assert re.search(rf'name="owners" {bound}\s+value="{CREATOR}"', card)
    # What the page was rendered with, so the route applies only this
    # page's changes.
    assert f'name="owners_original" value="{CREATOR}"' in card
    # The picker posts with Save, so an address typed and never added is
    # saved; it is not ``required``, or Save could not post the table.
    picker = _tag(card, 'id="owners-add-email"')
    assert 'name="owners"' in picker and bound in picker
    assert "required" not in picker


def test_the_card_is_editable_on_an_activated_session(
    client: TestClient, db: Session
) -> None:
    """Every lifecycle state, as the lobby's tags (author's ruling)."""
    review_session = _create(client, db, "OWN-CARD-4")
    review_session.status = "ready"
    db.commit()
    card = _card(_home(client, review_session))

    assert "data-owners-remove" in card
    assert "data-owners-add" in card
    assert "disabled" not in _tag(card, "data-owners-save")


def test_save_submits_the_card_and_cancel_resets_it(
    client: TestClient, db: Session
) -> None:
    """Both Secondary. Rendered enabled so the card saves without
    JavaScript; the page's script disables them until a change."""
    review_session = _create(client, db, "OWN-CARD-5")
    card = _card(_home(client, review_session))
    bound = f'form="owners-save-{review_session.id}"'

    save = _tag(card, "data-owners-save")
    cancel = _tag(card, "data-owners-cancel")
    assert 'type="submit"' in save and bound in save
    assert 'type="reset"' in cancel and bound in cancel
    for tag in (save, cancel):
        assert 'class="btn secondary"' in tag
        assert "disabled" not in tag


def test_the_gating_script_is_on_the_page(client: TestClient, db: Session) -> None:
    review_session = _create(client, db, "OWN-CARD-6")
    body = _home(client, review_session)

    assert "document.querySelectorAll('[data-owners-stager]')" in body
    assert "function syncRemoves()" in body
    assert "window.confirm(" in body
    gate = body[body.index('document.getElementById("owners-card")') :]
    assert 'form.addEventListener("reset"' in gate
    assert "button.disabled = !dirty" in gate


def test_the_staging_buttons_ship_hidden(client: TestClient, db: Session) -> None:
    """Without JavaScript they would do nothing; the stager shows them."""
    review_session = _create(client, db, "OWN-CARD-7")
    _add_bob(db, review_session)
    card = _card(_home(client, review_session))

    add = _tag(card, "data-owners-add")
    assert "hidden" in add and 'class="btn secondary"' in add
    removes = re.findall(r"<button[^>]*data-owners-remove[^>]*>", card)
    assert len(removes) == 2
    assert all("hidden" in tag for tag in removes)


def test_without_javascript_other_owners_can_be_removed(
    client: TestClient, db: Session
) -> None:
    """A ``<noscript>`` Remove posts to the old route, saved at once —
    on bob's row, not on your own."""
    review_session = _create(client, db, "OWN-CARD-8")
    bob = _add_bob(db, review_session)
    card = _card(_home(client, review_session))

    fallbacks = re.findall(r"<noscript>.*?</noscript>", card, re.S)
    assert len(fallbacks) == 1
    assert (
        f'action="/operator/sessions/{review_session.id}/owners/{bob.id}/remove"'
        in fallbacks[0]
    )


def test_without_javascript_the_last_owner_has_no_remove(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "OWN-CARD-9")
    card = _card(_home(client, review_session))

    assert "<noscript>" not in card


def test_candidates_are_every_workspace_operator(
    client: TestClient, db: Session
) -> None:
    """Current owners included, so a staged-out owner can be picked again
    before Save (author's ruling)."""
    review_session = _create(client, db, "OWN-CARD-10")
    _add_bob(db, review_session)
    card = _card(_home(client, review_session))
    datalist = card[card.index('<datalist id="owners-candidates">') :]
    datalist = datalist[: datalist.index("</datalist>")]

    assert f'value="{CREATOR}"' in datalist
    assert 'value="bob@example.edu"' in datalist


def test_create_ships_its_add_owner_hidden_too(
    client: TestClient, db: Session, bob
) -> None:
    """The shared stager shows the button; without JavaScript it does
    nothing on Create either."""
    db.add(User(email="bob@example.edu", is_operator=True))
    db.commit()
    body = client.get("/operator/sessions/new").text

    assert re.search(r'id="session-owners-add" data-owners-add hidden>', body)
