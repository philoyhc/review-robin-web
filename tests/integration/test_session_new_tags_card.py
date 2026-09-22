"""Segment 19S Item 6 rung 1 — the Tags card on
``/operator/sessions/new``, landed as a scaffold.

`CLAUDE.md` requires a new card to land inert first: real copy and
layout, no behaviour. So these tests assert two things at once — that
the card is *there*, and that it does **nothing** — and the second half
is what rung 2 will deliberately flip.

Inertness is not a comment here, it is a property with two halves:

* the input carries no ``name``, so a browser does not submit it;
* it carries no ``form="create-session-form"``, which is what
  associates a control outside the ``<form>`` with it — every live
  control in the bottom row has one.

Either alone would leave the control half-wired, so both are asserted,
and a round-trip through ``POST /operator/sessions`` confirms the
created session has no tags whatever the page renders.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from app.services import session_tags


def _card(body: str) -> str:
    """The Tags card's markup, from its anchor to the end of the row."""
    start = body.find('id="session-tags"')
    assert start != -1, "the Tags card is missing from the page"
    return body[start:]


def test_the_tags_card_renders_below_user_interface_settings(
    client: TestClient,
) -> None:
    """The card sits in the bottom row's right column, under the
    UI-settings card, per the plan's `Decision`."""
    body = client.get("/operator/sessions/new").text

    ui_pos = body.find('id="user-interface-settings"')
    tags_pos = body.find('id="session-tags"')
    assert -1 not in (ui_pos, tags_pos)
    assert ui_pos < tags_pos, "Tags sits below User interface settings"

    card = _card(body)
    assert "<h3" in card and "Tags</h3>" in card
    assert "Comma-separated" in card, "the copy says how to type two"


def test_the_tags_input_is_inert(client: TestClient) -> None:
    """Rung 1 ships the control unwired, both ways it could be wired.

    This is the assertion rung 2 inverts, so it is written to fail the
    moment the input becomes live rather than to describe the markup:
    a ``name`` is what a browser submits, and a ``form=`` is what
    associates a control rendered outside ``<form>`` with it.
    """
    body = client.get("/operator/sessions/new").text
    card = _card(body)

    assert 'name="tags"' not in card, (
        "the scaffold's input must not be named — a named input is "
        "submitted, which is rung 2's change and not rung 1's"
    )
    assert 'form="create-session-form"' not in card, (
        "the scaffold's input must not be associated with the create "
        "form; every live control in this row carries that attribute"
    )
    # ...and the control is genuinely there to be wired, so that the two
    # assertions above cannot pass by the card being empty.
    assert 'id="tags"' in card and "<input" in card


def test_creating_a_session_through_the_page_writes_no_tags(
    client: TestClient, db: Session
) -> None:
    """The round trip, which is the half a markup assertion cannot make.

    Posting the field the rung-2 input *will* carry leaves the created
    session untagged, because nothing reads it yet. Rung 2 makes this
    test's final assertion false by design.
    """
    response = client.post(
        "/operator/sessions",
        data={
            "name": "Scaffold",
            "code": "tags-scaffold",
            "description": "",
            "tags": "pilot, 2026",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    created = db.execute(
        select(ReviewSession).where(ReviewSession.code == "tags-scaffold")
    ).scalar_one()
    # ``tags_for_sessions`` keys every id it is asked about, so the
    # empty state is an empty *list*, not an absent key — checked
    # against the helper rather than assumed, which is the habit
    # `docs/unenforced_conventions.md` §1.11 is about.
    assert session_tags.tags_for_sessions(db, [created.id]) == {
        created.id: []
    }, "rung 1 writes no tags; the field is not read yet"
