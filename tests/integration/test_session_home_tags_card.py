"""19S Item 9 Part B rung 1 — the Tags card on Session Home, as a scaffold.

The card renders below User interface settings in the details card's
right-hand ``.bottom-left`` column, above the Save / Cancel / Lock
cluster. Locked it shows the session's tags as a ``.config-value``, like
every other field on that card; unlocked it shows a text input
prefilled with the same comma-joined string.

**This rung is deliberately inert, and these tests pin inertness as a
property.** The input carries no ``name`` — so a browser does not submit
it — and no ``form=`` — which is what associates a control rendered
outside ``<form>`` with the card's ``config-save`` form. Either alone
would leave the control half-wired, so both absences are asserted, and a
round trip through ``POST /sessions/{id}/config`` carrying ``tags=``
confirms the route ignores it. Rung 2 inverts all three by design.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.services import session_tags


def _create(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Tagged", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _tag(db: Session, review_session: ReviewSession, tags: list[str]) -> None:
    user = db.execute(select(User)).scalars().first()
    session_tags.set_tags(db, review_session=review_session, user=user, tags=tags)


def _card(body: str) -> str:
    """The Tags card's own markup — opening tag to its closing one.

    A ``<div>`` depth scan, the shape 19S Item 6's review settled on:
    bounding at the next sibling card falls back to the page's tail when
    there is none, and every ``in card`` assertion then reads the rest of
    the document. ``test_the_card_helper_is_bounded`` guards it.
    """
    anchor = body.find('id="config-tags-card"')
    assert anchor != -1, "the Tags card is missing from Session Home"
    start = body.rfind("<div", 0, anchor)
    depth = 0
    i = start
    while True:
        opened = body.find("<div", i)
        closed = body.find("</div>", i)
        assert closed != -1, "the Tags card's <div> is never closed"
        if opened != -1 and opened < closed:
            depth += 1
            i = opened + len("<div")
            continue
        depth -= 1
        i = closed + len("</div>")
        if depth == 0:
            return body[start:i]


def test_the_card_helper_is_bounded(client: TestClient, db: Session) -> None:
    """Balanced, and something rendered follows it: the card is not the
    page's last element, so a tail slice would carry the Save cluster."""
    review_session = _create(client, db, "HOME-TAGS-BOUND")
    body = client.get(f"/operator/sessions/{review_session.id}").text
    card = _card(body)

    assert card.startswith('<div class="card" id="config-tags-card"')
    assert card.count("<div") == card.count("</div>")
    assert "data-config-save" not in card, (
        "the Save cluster follows the card and is not inside it"
    )
    assert "data-config-save" in body[body.index(card) + len(card):]


def test_the_card_sits_below_ui_settings_and_above_the_save_cluster(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "HOME-TAGS-ORDER")
    body = client.get(f"/operator/sessions/{review_session.id}").text

    ui = body.find('id="config-ui-settings-card"')
    tags = body.find('id="config-tags-card"')
    save = body.find("data-config-save")
    assert -1 not in (ui, tags, save)
    assert ui < tags < save

    # Same .bottom-left column as the UI settings card, so the column's
    # gap spaces the pair (spec/ui_elements.md §10) — no new CSS.
    column = body.rfind('<div class="bottom-left">', 0, ui)
    assert column != -1
    assert body.rfind('<div class="bottom-left">', 0, tags) == column


def test_locked_it_renders_like_the_other_fields(
    client: TestClient, db: Session
) -> None:
    """A ``.config-value``, display-only, holding the tags comma-joined —
    the treatment ``help_contact`` and ``description`` already have."""
    review_session = _create(client, db, "HOME-TAGS-LOCKED")
    _tag(db, review_session, ["pilot", "2026"])
    card = _card(client.get(f"/operator/sessions/{review_session.id}").text)

    assert '<div class="config-value" data-display-only>2026, pilot</div>' in card
    assert "Tags (optional)</h3>" in card
    # The heading is the label; there is no second "Tags" above the box.
    assert "<label" not in card
    assert 'aria-labelledby="config-tags-heading"' in card


def test_an_untagged_session_shows_an_em_dash(
    client: TestClient, db: Session
) -> None:
    review_session = _create(client, db, "HOME-TAGS-EMPTY")
    card = _card(client.get(f"/operator/sessions/{review_session.id}").text)

    assert '<div class="config-value" data-display-only>—</div>' in card
    assert 'value=""' in card, "and the edit box starts empty"


def test_unlocked_the_input_is_prefilled(client: TestClient, db: Session) -> None:
    review_session = _create(client, db, "HOME-TAGS-EDIT")
    _tag(db, review_session, ["pilot", "2026"])
    body = client.get(f"/operator/sessions/{review_session.id}?editing=1").text
    card = _card(body)

    assert 'data-config-mode="edit"' in body
    assert 'value="2026, pilot"' in card
    assert "data-edit-only" in card


def test_the_input_is_inert(client: TestClient, db: Session) -> None:
    """Both halves of inertness, asserted as absences. Rung 2 inverts
    them, so the diff shows the control going live."""
    review_session = _create(client, db, "HOME-TAGS-INERT")
    card = _card(
        client.get(f"/operator/sessions/{review_session.id}?editing=1").text
    )

    assert 'id="config-tags"' in card, "the control is genuinely there"
    assert 'name="tags"' not in card
    assert "form=" not in card


def test_saving_the_card_with_a_tags_field_changes_nothing(
    client: TestClient, db: Session
) -> None:
    """The half no markup assertion can make: even a request that does
    carry ``tags=`` leaves the session's tags as they were.

    The rename is the control. A 303 alone would also be what a rejected
    save returns, and a rejected save leaves tags alone for the wrong
    reason — so the test first establishes the save really happened.
    """
    review_session = _create(client, db, "HOME-TAGS-POST")
    _tag(db, review_session, ["pilot"])
    response = client.post(
        f"/operator/sessions/{review_session.id}/config",
        data={
            "name": "Renamed",
            "code": "HOME-TAGS-POST",
            "description": "",
            "display_timezone": "",
            "tags": "other, stuff",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    assert "error" not in response.headers["location"]
    db.refresh(review_session)
    assert review_session.name == "Renamed", "the save went through"
    assert session_tags.tags_for_sessions(db, [review_session.id])[
        review_session.id
    ] == ["pilot"]
