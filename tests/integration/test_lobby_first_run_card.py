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
    assert "You don't have any sessions yet" in body


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
    # The stats pills stay. They used to live inside the populated branch
    # and vanished with the table, which is the Known gap
    # `spec/sessions_overview.md` recorded: an operator who archived
    # everything lost both the count and the route to it. The cards now
    # render in every state, so the count survives...
    assert "1 archived" in body
    # ...and so does the way back to it.
    assert 'href="/operator/sessions/archived"' in body


def test_the_empty_lobby_still_shows_both_cards(client: TestClient) -> None:
    """Standardized 2026-09-07: Sessions + Search render in every state, so
    the lobby has one shape an operator learns rather than two. Before this
    the whole row lived inside the populated branch and simply disappeared."""
    body = client.get("/operator/sessions").text

    assert 'class="card sessions-lobby-card"' in body
    assert 'class="card sessions-action-card"' in body
    assert "0 sessions" in body
    assert CARD_MARKER in body  # the first-run card sits below them


def test_the_empty_lobby_leaves_only_the_two_ways_out_active(
    client: TestClient,
) -> None:
    """Search and Cancel have nothing to act on, so they go inert. The three
    navigations stay live: `Add new session` and `Rehydrate` are how an
    operator gets *out* of an empty lobby, and `Go to Archive` is always
    active — an empty archive page beats a dead control, and it is one
    fewer rule to reason about.

    Inert controls are `<span>`s, not disabled anchors: `a.btn.disabled`
    dims and changes the cursor but does not set `pointer-events: none`, so
    a disabled anchor would still navigate.
    """
    body = client.get("/operator/sessions").text

    assert 'href="/operator/sessions/new">Add new session</a>' in body
    assert 'href="/operator/sessions/rehydrate"' in body
    assert 'href="/operator/sessions/archived"' in body

    # Whitespace-normalised: the template wraps these attributes, and
    # re-wrapping should not break the test.
    flat = " ".join(body.split())
    assert (
        '<span class="btn secondary disabled" aria-disabled="true">'
        "Cancel</span>" in flat
    )
    assert 'aria-label="Search sessions" disabled>' in flat


def test_the_card_lays_its_four_steps_out_as_sub_cards(
    client: TestClient,
) -> None:
    """Four tiles across, not the numbered list this was until 2026-09-07.

    A list is read top-to-bottom and its last item is read least, and the
    last of these steps — getting the data back out — is the one an
    operator most wants reassurance about *before* starting. Four tiles of
    equal width say "four ordinary stages"; a 1-2-3-4 list says the fourth
    one is furthest away.
    """
    body = client.get("/operator/sessions").text
    flat = " ".join(body.split())

    assert '<div class="subcard-row stepped">' in flat
    # Tiles are the app's existing help cards, not a tile look of their own:
    # a row of tiles inside a card is explaining something, which is what
    # `.rs-help-card` already says. A short-lived `.subcard` class that
    # duplicated `.data-shape-card`'s shape was retired the same day.
    assert flat.count('<div class="card rs-help-card">') == 4
    assert '<div class="subcard">' not in flat
    # The list it replaced is gone, not merely hidden.
    assert "<ol>" not in flat.split(CARD_MARKER, 1)[1].split("</div>")[0]

    # The definition of a session sits under the card header, not inside the
    # first tile: it is what all four tiles are about, so it belongs to the
    # card. It must land before the row, not within it.
    card = flat.split(CARD_MARKER, 1)[1]
    definition = "A <strong>session</strong> is one review round with its own"
    assert definition in card
    assert card.index(definition) < card.index('<div class="subcard-row stepped">')


def test_the_four_steps_are_separated_by_arrows(client: TestClient) -> None:
    """Three arrows, not four: the tiles are a sequence, and a trailing
    arrow after the last one would point at nothing.

    They are decorative and marked so. The order is already carried by
    reading order, which is what a screen reader uses; announcing "right
    arrow" three times between four headings would only add noise. The
    `.stepped` modifier is what makes room for them — it interleaves an
    `auto` track after each tile — so the class and the spans have to
    travel together.
    """
    flat = " ".join(client.get("/operator/sessions").text.split())

    assert '<div class="subcard-row stepped">' in flat
    assert flat.count('<span class="subcard-arrow" aria-hidden="true">') == 3

    # Each arrow sits *between* two tiles — never before the first or
    # after the last. Splitting the row on the arrows must leave four
    # segments holding one tile each; a leading or trailing arrow would
    # produce an empty segment.
    row = flat.split('<div class="subcard-row stepped">', 1)[1]
    row = row[: row.index("</div> </div>")]
    segments = row.split('<span class="subcard-arrow" aria-hidden="true">→</span>')
    assert len(segments) == 4
    for segment in segments:
        assert segment.count('<div class="card rs-help-card">') == 1


# Each of the card's four sub-cards is a table-of-contents entry for one
# Guide section. The two sides shared headings verbatim until the
# four-sub-card rewrite (2026-09-07) pulled three of them apart; the Guide
# rewrite later the same day pulled them back, because the author's own
# draft of the Guide reached for the card's vocabulary unprompted. Three
# of four now match exactly.
#
# The mapping stays written down rather than collapsing to "these strings
# are equal", because the one remaining divergence is deliberate: the card
# is read by someone who has not yet made a session, so its tile says
# "Set up a session", while the Guide section covers creating one as well.
# Rename a heading on either side without touching its partner and this
# fails, which is the drift the test was always for.
CARD_STEP_TO_GUIDE_SECTION = {
    "Set up a session": "Create and set up a session",
    "Prepare and activate": "Prepare and activate",
    "Give reviewers access": "Give reviewers access",
    "Download responses": "Download responses",
}


def test_the_card_reuses_the_guides_step_vocabulary(client: TestClient) -> None:
    """The card is a table of contents for the Guide, not a second account
    of the workflow. Every step it names must still have a Guide section
    behind it, and vice versa."""
    lobby = client.get("/operator/sessions").text
    guide = client.get("/guide").text

    for card_step, guide_section in CARD_STEP_TO_GUIDE_SECTION.items():
        assert f"<h3>{card_step}</h3>" in lobby, card_step
        assert f"<h2>{guide_section}</h2>" in guide, guide_section


def test_an_all_archived_lobby_keeps_the_route_to_the_archive(
    client: TestClient, db: Session
) -> None:
    """The third lobby state, and the one that had no coverage: no live
    sessions, but archived ones exist.

    It is the state the Known gap was about. `Go to Archive` used to live
    inside the populated branch, so archiving the last session took away
    both the `N archived` count and the only in-app route to
    `/operator/sessions/archived` — the operator's sessions were still
    there and unreachable. Search and Cancel stay inert (there is nothing
    live to search), but the way back to the archive does not.
    """
    _create_session(client, "Only One", "only-1")
    session_id = db.execute(
        select(ReviewSession.id).where(ReviewSession.code == "only-1")
    ).scalar_one()
    client.post(
        "/operator/sessions/bulk-archive",
        data={"session_ids": [session_id]},
        follow_redirects=False,
    )
    db.expire_all()

    flat = " ".join(client.get("/operator/sessions").text.split())

    assert "1 archived" in flat
    assert 'href="/operator/sessions/archived">Go to Archive</a>' in flat
    # Still nothing live to search.
    assert (
        '<span class="btn secondary disabled" aria-disabled="true">'
        "Cancel</span>" in flat
    )
    assert 'aria-label="Search sessions" disabled>' in flat
