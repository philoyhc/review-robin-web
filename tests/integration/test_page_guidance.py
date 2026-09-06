"""Page-level guidance disclosures — Segment 19E rung 6.

Rung 6 lands in two stages: this pilot wires the scaffold on one Setup
page (Email Template) so its shape can be reviewed before the remaining
five pages take it. These tests therefore cover the *scaffold* — the
macro's chrome, and the deep-link contract it depends on — rather than
just the one page's copy.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from app.web.views._guide import SECTIONS


def _session_id(client: TestClient, db: Session) -> int:
    client.post(
        "/operator/sessions",
        data={"name": "Guidance", "code": "guidance-1"},
        follow_redirects=False,
    )
    return db.execute(
        select(ReviewSession.id).where(ReviewSession.code == "guidance-1")
    ).scalar_one()


def test_the_email_template_page_carries_one_guidance_disclosure(
    client: TestClient, db: Session
) -> None:
    body = client.get(
        f"/operator/sessions/{_session_id(client, db)}/setup-invite"
    ).text

    assert body.count('<details class="page-guidance">') == 1
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

    assert "<details class='page-guidance' open" not in body
    assert '<details class="page-guidance" open' not in body


def test_the_guidance_sits_above_the_template_selector(
    client: TestClient, db: Session
) -> None:
    """Page-level guidance explains the page, not the selected tab, so
    it precedes the tab strip that chooses which email is being
    edited."""
    body = client.get(
        f"/operator/sessions/{_session_id(client, db)}/setup-invite"
    ).text

    assert body.index('class="page-guidance"') < body.index(
        'class="tab-strip tab-strip-page"'
    )


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
