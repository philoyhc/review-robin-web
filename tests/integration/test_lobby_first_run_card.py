"""The sessions-lobby first-run card — Segment 19E rung 3.

The card replaces the plain empty state on `/operator/sessions`. Its job
is to make `/guide` findable at the one moment orientation is most
wanted, so these tests care about two things: that the trigger is the
zero-visible-sessions state the plan specifies (not "has never had a
session"), and that the Guide link it carries actually resolves.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession

CARD_MARKER = 'id="lobby-first-run"'
GUIDE_LINK = '/guide?return_to=/operator/sessions'


def _create_session(client: TestClient, name: str, code: str) -> None:
    client.post(
        "/operator/sessions",
        data={"name": name, "code": code},
        follow_redirects=False,
    )


def test_operator_with_no_sessions_sees_the_card(client: TestClient) -> None:
    body = client.get("/operator/sessions").text

    assert CARD_MARKER in body
    assert "You don't have any sessions yet." in body


def test_the_card_carries_a_link_to_the_guide(client: TestClient) -> None:
    """The card exists to make `/guide` findable — the chrome link alone
    is easy to miss on a first visit.

    The two links are byte-identical (both
    `/guide?return_to=/operator/sessions`, the chrome deriving its
    `return_to` from the current path), so a plain substring check would
    pass on the chrome's link alone and prove nothing about the card.
    Counting is what separates them.
    """
    empty = client.get("/operator/sessions").text
    assert empty.count(GUIDE_LINK) == 2  # chrome + card

    _create_session(client, "Spring Reviews", "spring-2026")

    populated = client.get("/operator/sessions").text
    assert populated.count(GUIDE_LINK) == 1  # chrome only


def test_the_guide_link_resolves_and_returns_to_the_lobby(
    client: TestClient,
) -> None:
    """A dead or unallowlisted `return_to` fails silently — the Guide
    would render with a Back link to the default target and nobody would
    notice. Follow the link rather than trusting the string."""
    response = client.get(GUIDE_LINK)

    assert response.status_code == 200
    assert "&larr; Back to Sessions" in response.text or (
        "← Back to Sessions" in response.text
    )


def test_operator_with_a_session_does_not_see_the_card(
    client: TestClient,
) -> None:
    _create_session(client, "Spring Reviews", "spring-2026")

    body = client.get("/operator/sessions").text

    assert CARD_MARKER not in body


def test_the_populated_lobby_still_renders_its_table_and_search(
    client: TestClient,
) -> None:
    """Guards the other side of the `{% if sessions %}` branch the card
    hangs off: rung 3 must not disturb the table or the filters."""
    _create_session(client, "Spring Reviews", "spring-2026")

    body = client.get("/operator/sessions").text

    assert 'data-rrw-sortable="rrw-sort-lobby"' in body
    assert "Search by name, code, or tag" in body
    assert "Spring Reviews" in body


def test_archiving_every_session_brings_the_card_back(
    client: TestClient, db: Session
) -> None:
    """The trigger is zero *visible* sessions, not "has never had one" —
    an operator who archives everything is back at the start and gets the
    orientation again (`guide/segment_19E_operator_onboarding.md` ->
    Semantics, "Lobby card trigger")."""
    _create_session(client, "Archive Me", "arch-me")
    session_id = db.execute(
        select(ReviewSession.id).where(ReviewSession.code == "arch-me")
    ).scalar_one()
    assert CARD_MARKER not in client.get("/operator/sessions").text

    client.post(
        "/operator/sessions/bulk-archive",
        data={"session_ids": [session_id]},
        follow_redirects=False,
    )

    db.expire_all()
    assert db.get(ReviewSession, session_id).status == "archived"

    body = client.get("/operator/sessions").text
    assert CARD_MARKER in body
    # The stats pills — including the "N archived" count — live in the
    # populated branch, so they vanish along with the table.
    assert "1 archived" not in body


def test_the_card_reuses_the_guides_step_vocabulary(client: TestClient) -> None:
    """The card is a table of contents for the Guide, not a second account
    of the workflow. If a Guide heading is reworded and the card is not,
    the two drift into different vocabularies for the same step."""
    lobby = client.get("/operator/sessions").text
    guide = client.get("/guide").text

    for phrase in ("Create and set", "Prepare and launch", "Give reviewers access"):
        assert phrase in lobby, phrase
        assert phrase in guide, phrase
