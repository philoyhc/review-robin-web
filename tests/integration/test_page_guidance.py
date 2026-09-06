"""Page-level guidance disclosures — Segment 19E rung 6.

Rung 6 lands in two stages: this pilot wires the scaffold on one Setup
page (Email Template) so its shape can be reviewed before the remaining
five pages take it. These tests therefore cover the *scaffold* — the
macro's chrome, and the deep-link contract it depends on — rather than
just the one page's copy.
"""

from __future__ import annotations

from html.parser import HTMLParser

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from app.web.views._guide import SECTIONS


#: Markup-only marker. The bare class name also appears ~9 times in
#: base.html's stylesheet, so counting that counts CSS rules.
CARD = '<details class="card page-guidance'


def _session_id(client: TestClient, db: Session) -> int:
    client.post(
        "/operator/sessions",
        data={"name": "Guidance", "code": "guidance-1"},
        follow_redirects=False,
    )
    return db.execute(
        select(ReviewSession.id).where(ReviewSession.code == "guidance-1")
    ).scalar_one()


def test_the_email_template_page_carries_one_guidance_card(
    client: TestClient, db: Session
) -> None:
    body = client.get(
        f"/operator/sessions/{_session_id(client, db)}/setup-invite"
    ).text

    assert body.count(CARD) == 1
    assert "<summary>What this page is for</summary>" in body


def test_the_disclosure_is_closed_by_default(
    client: TestClient, db: Session
) -> None:
    """An operator who knows the page should not scroll past a paragraph
    they have read. `<details>` without `open` is closed — asserted
    because adding `open` is a one-word change that would go unnoticed."""
    body = client.get(
        f"/operator/sessions/{_session_id(client, db)}/setup-invite"
    ).text

    assert CARD in body
    # The attribute would land inside the opening tag, whatever classes
    # precede it — so check the tag itself rather than a fixed string.
    opening_tag = body[body.index(CARD) :].split(">", 1)[0]
    assert "open" not in opening_tag


def test_the_guidance_sits_above_the_merge_tags_card(
    client: TestClient, db: Session
) -> None:
    """The right column stacks guidance above the merge-tag reference it
    introduces. Supersedes rung 6a's "above the tab strip" placement,
    which the author replaced when the help cards became half-width
    cards (see the segment plan's `## Status`)."""
    body = client.get(
        f"/operator/sessions/{_session_id(client, db)}/setup-invite"
    ).text

    assert body.index(CARD) < body.index('id="merge-tags"')


def test_the_guidance_links_into_the_guide_and_returns_here(
    client: TestClient, db: Session
) -> None:
    """The rung's rule is that guidance links to the Guide rather than
    restating it. Both halves of the link matter: the fragment has to
    name a real section, and the `return_to` has to survive the
    allowlist so the operator lands back on this page."""
    session_id = _session_id(client, db)
    page = f"/operator/sessions/{session_id}/setup-invite"

    body = client.get(page).text
    assert f'href="/guide?return_to={page}#guide-give_access"' in body

    guide = client.get(f"/guide?return_to={page}")
    assert guide.status_code == 200
    assert 'id="guide-give_access"' in guide.text
    # A path outside the allowlist silently falls back to the lobby, so
    # assert the Back link actually names this session rather than
    # trusting that the URL was accepted.
    assert "Back to Guidance" in guide.text


def test_every_guide_section_card_carries_its_anchor(client: TestClient) -> None:
    """Guidance on the remaining five pages will deep-link to other
    sections. Each card's id is derived from the same key the view gates
    on, so a renamed section breaks the anchor here rather than becoming
    a dead link in production."""
    body = client.get("/guide").text

    missing = [s.key for s in SECTIONS if f'id="guide-{s.key}"' not in body]
    assert not missing, f"guide sections with no anchor: {missing}"


# --------------------------------------------------------------------------- #
# Rung 6b scaffold — placement across all six Setup pages
# --------------------------------------------------------------------------- #

#: Pages reachable on a plain draft session. Relationships and Observers
#: are gated on per-session toggles and are covered separately.
SETUP_PAGES = ("reviewers", "reviewees", "instruments", "setup-invite")

#: The two gated Setup pages, with the session flag each needs.
GATED_SETUP_PAGES = (
    ("relationships", "relationships_enabled"),
    ("observers", "observers_enabled"),
)


def test_every_setup_page_carries_exactly_one_guidance_card(
    client: TestClient, db: Session
) -> None:
    """One per page is the scaffold's contract — the disclosure is a
    page-level affordance, and two of them on one page would make
    neither the place to look."""
    session_id = _session_id(client, db)

    for page in SETUP_PAGES:
        body = client.get(f"/operator/sessions/{session_id}/{page}").text

        assert body.count(CARD) == 1, page
        assert "<summary>What this page is for</summary>" in body, page


def test_the_gated_setup_pages_carry_one_too(
    client: TestClient, db: Session
) -> None:
    """Relationships and Observers 404 until their session toggle is on,
    so they need the flag set rather than riding the loop above. Both are
    Setup pages and both take the scaffold."""
    session_id = _session_id(client, db)

    for page, flag in GATED_SETUP_PAGES:
        review_session = db.get(ReviewSession, session_id)
        setattr(review_session, flag, True)
        db.flush()

        response = client.get(f"/operator/sessions/{session_id}/{page}")

        assert response.status_code == 200, page
        assert response.text.count(CARD) == 1, page


def test_the_guidance_card_is_a_card(client: TestClient, db: Session) -> None:
    """The author's decision: these are half-width cards, not inline
    disclosures. Width comes from the grid slot each page puts them in,
    so what is asserted here is the card class the styling hangs off."""
    body = client.get(
        f"/operator/sessions/{_session_id(client, db)}/reviewers"
    ).text

    assert CARD in body


def test_the_instruments_bulk_toggles_moved_into_the_deadline_card(
    client: TestClient, db: Session
) -> None:
    """Their old card became the guidance card. The buttons still have to
    be on the page and ahead of the guidance — losing them would be a
    silent regression, since nothing else expands an instrument card."""
    body = client.get(
        f"/operator/sessions/{_session_id(client, db)}/instruments"
    ).text

    assert "data-instruments-expand-all" in body
    assert "data-instruments-collapse-all" in body
    assert body.index("Session deadline") < body.index(
        "data-instruments-expand-all"
    )
    assert body.index("data-instruments-expand-all") < body.index(CARD)


# --------------------------------------------------------------------------- #
# Column stacks — 19E rung 6b tweak
# --------------------------------------------------------------------------- #

_VOID_ELEMENTS = frozenset(
    "area base br col embed hr img input link meta param source track wbr".split()
)


class _NestingCheck(HTMLParser):
    """Reports tags closed out of order, and tags left open at EOF."""

    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag not in _VOID_ELEMENTS:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in _VOID_ELEMENTS:
            return
        if not self.stack:
            self.errors.append(f"</{tag}> with nothing open")
        elif self.stack[-1] != tag:
            self.errors.append(f"</{tag}> closed <{self.stack[-1]}>")
            if tag in self.stack:
                while self.stack and self.stack.pop() != tag:
                    pass
        else:
            self.stack.pop()


def test_every_setup_page_nests_correctly(
    client: TestClient, db: Session
) -> None:
    """Wrapping cards in column stacks means hand-balancing `<div>`s
    across Jinja conditionals, and an unbalanced one renders a page that
    still returns 200 and still contains every string a content test
    looks for — the layout is simply wrong. This is the check that
    catches it: it found a missing `</div>` on three pages that the rest
    of the suite passed clean.
    """
    session_id = _session_id(client, db)
    review_session = db.get(ReviewSession, session_id)
    review_session.observers_enabled = True
    review_session.relationships_enabled = True
    db.flush()

    for page in (*SETUP_PAGES, "relationships", "observers"):
        parser = _NestingCheck()
        parser.feed(client.get(f"/operator/sessions/{session_id}/{page}").text)

        assert parser.errors == [], (page, parser.errors)
        assert parser.stack == [], (page, parser.stack)


def test_the_observers_guidance_leads_the_left_column(
    client: TestClient, db: Session
) -> None:
    """Top left, above the cohort editor and in the same column — so
    opening it pushes the cohort editor down and leaves the Operator
    actions card in the right column untouched."""
    session_id = _session_id(client, db)
    review_session = db.get(ReviewSession, session_id)
    review_session.observers_enabled = True
    db.flush()

    body = client.get(f"/operator/sessions/{session_id}/observers").text

    # Markup markers, not bare class names: both classes are also
    # styled in base.html, and a bare-name index finds the stylesheet.
    assert body.index(CARD) < body.index('id="observers-cohort-heading"')
    assert body.index(CARD) < body.index('class="card operator-actions-card"')


def test_the_column_stacks_are_start_aligned(client: TestClient) -> None:
    """`align-items: start` is what makes the two columns independent —
    the grid default, `stretch`, would make both as tall as the taller
    and defeat the whole point."""
    body = client.get("/guide").text  # any page: the rule lives in base.html

    assert ".card-columns {" in body
    columns_rule = body.split(".card-columns {")[1].split("}")[0]
    assert "align-items: start" in columns_rule


ROSTER_PAGES = ("reviewers", "reviewees", "relationships")


def test_the_roster_pages_put_every_top_card_in_one_column_container(
    client: TestClient, db: Session
) -> None:
    """All four cards above the preview table share one `.card-columns`,
    not two stacked row grids.

    Two containers would look identical when everything is closed and
    still fail the point of the change: growth in the upper one pushes
    *both* columns of the lower one down. So this asserts the source
    order that only a single container with two column stacks produces —
    the whole left column, then the whole right.
    """
    session_id = _session_id(client, db)
    review_session = db.get(ReviewSession, session_id)
    review_session.relationships_enabled = True
    db.flush()

    for page in ROSTER_PAGES:
        body = client.get(f"/operator/sessions/{session_id}/{page}").text
        assert body.count('class="card-columns"') == 1, page

        # Left column in full, then right column in full — the source
        # order only a single container of two column stacks produces.
        order = [
            body.index(CARD),
            body.index("field-labels-form"),
            body.index("Fields with data:"),
            body.index('class="card operator-actions-card"'),
        ]
        assert order == sorted(order), (page, order)

        # No row grid above those four. The Upload / Danger Zone pair
        # below still is a `.bottom-grid` and should be — asserting
        # position rather than absence keeps this independent of whether
        # the preview table rendered.
        assert body.index('class="bottom-grid"') > order[-1], page


def test_the_activated_lock_card_sits_above_the_columns(
    client: TestClient, db: Session
) -> None:
    """It is full width, and `.card-columns` has no spanning slot — a
    full-width card between the two pairs is what forced them into two
    separate row grids before. Above the container it reads at the top
    of the page, which is where an "you cannot edit this" notice
    belongs."""
    session_id = _session_id(client, db)
    review_session = db.get(ReviewSession, session_id)
    review_session.status = "ready"
    db.flush()

    body = client.get(f"/operator/sessions/{session_id}/reviewers").text

    assert 'class="card lock"' in body
    assert body.index('class="card lock"') < body.index('class="card-columns"')
