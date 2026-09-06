"""The `/guide` page scaffold — Segment 19E rung 1.

Covers the route, every committed section heading, the chrome link
behaving like `/about`'s, and the return-to-origin affordance.

Headings rather than prose, deliberately: the copy is editorial and will
be revised repeatedly before rung 7, and a test that pins paragraphs
turns every wording improvement into a test edit. What must not change
silently is which sections exist — see `SECTIONS`.
"""

from __future__ import annotations

import pathlib

import pytest
from fastapi.testclient import TestClient

from app.auth.identity import AuthenticatedUser
from app.web import routes_guide
from app.web.views._guide import (
    AUDIENCES,
    SECTIONS,
    visible_audiences,
    visible_sections,
)

REPO = pathlib.Path(__file__).resolve().parents[2]

# The headings the page commits to, in reading order. Rung 7 may narrow who
# sees which, but a section must not silently disappear — that is what pinning
# the list here catches. Named for headings so it does not collide with the
# view's SECTIONS, which carries the audience mapping.
SECTION_HEADINGS = (
    "What Review Robin Web does",
    "Create and set up a session",
    "Prepare and launch",
    "Give reviewers access",
    "Watch progress",
    "Close, release, and share results",
    "Tips and troubleshooting",
    "Sample session",
    "For reviewers",
    "For observers",
    "For reviewees",
)

#: Retired at 19E, and asserted gone rather than merely absent from the
#: list above: `test_guide_renders_every_committed_section` only checks
#: that every listed heading is present, so dropping a name from that
#: tuple would let a stale card keep rendering unnoticed.
RETIRED_SECTION_HEADINGS = ("Before you start", "Getting help")


def test_guide_renders(client: TestClient) -> None:
    response = client.get("/guide")
    assert response.status_code == 200
    assert "<h1>Guide</h1>" in response.text


def test_guide_renders_every_committed_section(client: TestClient) -> None:
    body = client.get("/guide").text
    missing = [s for s in SECTION_HEADINGS if f"<h2>{s}</h2>" not in body]
    assert not missing, f"missing Guide sections: {missing}"


def test_the_retired_sections_are_gone(client: TestClient) -> None:
    """`Before you start` moved to `/about` and `Getting help` folded into
    `Tips and troubleshooting` (19E, author). Both were removed on a
    reading of what the page owes a reader who is already inside the app,
    so a card reappearing is a regression rather than a revert."""
    body = client.get("/guide").text

    for heading in RETIRED_SECTION_HEADINGS:
        assert f"<h2>{heading}</h2>" not in body, heading


def test_the_retired_content_landed_where_it_was_moved_to(
    client: TestClient,
) -> None:
    """Deleting a card and moving one look identical on the Guide. These
    assert the other half — that the facts survived the move, on the page
    that now owns them."""
    about = client.get("/about").text
    assert "there is nothing to install" in about
    assert "single sign-on" in about
    assert "operator allowlist" in about

    tips = " ".join(client.get("/guide").text.split())
    assert (
        "<strong>The Validate page</strong> explains most setup problems in "
        "plain language. For anything else, contact your Review Robin Web "
        "administrator." in tips
    )


def test_guide_back_link_defaults_to_the_lobby(client: TestClient) -> None:
    body = client.get("/guide").text
    assert 'class="back-link"' in body
    assert 'href="/operator/sessions"' in body
    assert "Back to Sessions" in body


def test_guide_back_link_honours_a_valid_return_to(client: TestClient) -> None:
    body = client.get("/guide?return_to=%2Fme").text
    assert 'href="/me"' in body


def test_guide_back_link_rejects_an_off_allowlist_return_to(
    client: TestClient,
) -> None:
    """Same allowlist `/about` uses — an unknown path falls back, never echoes."""
    body = client.get("/guide?return_to=https%3A%2F%2Fevil.example.edu").text
    assert "evil.example.edu" not in body
    assert 'href="/operator/sessions"' in body


def test_chrome_offers_the_guide_link_from_another_page(client: TestClient) -> None:
    """Jinja's ``urlencode`` leaves ``/`` unescaped, as the existing Settings
    and About links in the same row already do — asserted as rendered, not as
    assumed."""
    body = client.get("/about").text
    assert 'href="/guide?return_to=/about"' in body


def test_chrome_omits_the_guide_link_on_the_guide_itself(client: TestClient) -> None:
    body = client.get("/guide").text
    assert 'class="chrome-link" href="/guide' not in body
    # /about's own link still shows — the two pages are siblings, not one
    # page absorbing the other.
    assert 'class="chrome-link" href="/about' in body



# --------------------------------------------------------------------
# The audience filter — Segment 19E rung 2.
#
# It runs today and resolves to "everything"; rung 7 replaces the resolver.
# These assert the seam is *live*, not merely present, so the path cannot
# rot between now and then.


def _viewer() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="guide-test", email="nobody@example.edu", name="Nobody"
    )


def test_every_audience_is_visible_before_rung_7() -> None:
    assert visible_audiences(_viewer()) == frozenset(AUDIENCES)


def test_every_declared_section_is_visible_before_rung_7() -> None:
    assert visible_sections(_viewer()) == frozenset(s.key for s in SECTIONS)


def test_the_template_gates_on_the_view_not_on_its_own_logic(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Narrowing the audience set must actually drop cards.

    The point of landing the filter early is that it is exercised. If the
    template stopped consulting `visible_sections`, every other test here
    would still pass — this one would not. Patched on `routes_guide`, which
    imported the symbol directly, so this also pins that the route is what
    feeds the template.
    """
    monkeypatch.setattr(
        routes_guide, "visible_sections", lambda user: frozenset({"for_observers"})
    )
    body = client.get("/guide").text
    assert "<h2>For observers</h2>" in body
    assert "<h2>For reviewers</h2>" not in body
    assert "<h2>What Review Robin Web does</h2>" not in body


def test_quickstart_retired_to_archive() -> None:
    """The move is part of the contract, not incidental tidying."""
    assert not (REPO / "docs" / "quickstart.md").exists()
    archived = REPO / "docs" / "archive" / "quickstart.md"
    assert archived.exists()
    assert "RETIRED" in archived.read_text().splitlines()[0]


def test_headings_and_audience_mapping_stay_in_step() -> None:
    """One list of headings, one of audiences — they describe the same page.

    Adding a card to the template and forgetting its `GuideSection` would
    leave it ungatable, and rung 7 would ship it to everyone regardless of
    audience. Deriving the count from both sides catches that at the point
    it is introduced rather than at the point it matters.
    """
    assert len(SECTION_HEADINGS) == len(SECTIONS)
