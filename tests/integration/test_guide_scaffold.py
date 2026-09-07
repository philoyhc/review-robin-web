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

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import Reviewee, Reviewer, ReviewSession, User
from app.web import routes_guide
from app.web.views._guide import (
    OPERATOR,
    REVIEWER,
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
    "Prepare and activate",
    "Give reviewers access",
    "Watch progress",
    "Download responses",
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


def test_every_committed_section_exists_in_the_template() -> None:
    """Every card the page commits to is still written.

    Split from the render check below at rung 7: once the filter narrows,
    no single viewer sees all eleven, so a render can no longer prove a
    card exists. Deleting a card would otherwise look identical to being
    filtered out of that viewer's page.
    """
    template = (
        REPO / "app" / "web" / "templates" / "guide.html"
    ).read_text()
    missing = [s for s in SECTION_HEADINGS if f"<h2>{s}</h2>" not in template]
    assert not missing, f"missing Guide sections: {missing}"


def test_guide_renders_exactly_the_sections_its_viewer_is_owed(
    client: TestClient,
) -> None:
    """And the render still has to agree with the view.

    The conftest viewer is an operator, so the eight operator cards render
    and the three role-addressed ones do not. Derived from `SECTIONS`
    rather than listed, so retagging a section's audience updates both
    sides at once — a hand-kept list here would just start lying.
    """
    body = client.get("/guide").text
    for heading, section in zip(SECTION_HEADINGS, SECTIONS, strict=True):
        rendered = f"<h2>{heading}</h2>" in body
        assert rendered is (section.audience == OPERATOR), (
            f"{heading!r} ({section.audience}) "
            f"{'rendered' if rendered else 'did not render'} for an operator"
        )


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


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    client.post(
        "/operator/sessions",
        data={"name": f"Guide {code}", "code": code},
        follow_redirects=False,
    )
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _viewer(
    db: Session, *, email: str = "nobody@example.edu", operator: bool = False
) -> User:
    user = User(
        email=email,
        display_name="Nobody",
        external_principal_id=f"guide-test-{email}",
        is_operator=operator,
        is_sys_admin=False,
    )
    db.add(user)
    db.flush()
    return user


def test_a_viewer_holding_no_role_sees_nothing(db: Session) -> None:
    """**Inverted at 19F PR 3**, and the previous version is worth
    stating because it was a considered position, not an oversight.

    It read *"a viewer holding no role sees everything"*: 19E rung 7
    argued that such a person is not a reviewer being spared the
    operator walkthrough but someone the app cannot classify, usually
    about to be rostered — and that since the Guide carries no session
    data, too much beat nothing.

    The author reversed it a day later on a simpler observation: it made
    no sense for a stranger to see **more** of the Guide than any
    role-holder does. A reviewer sees one section; a stranger saw all
    eleven.

    The assertion is rewritten in place rather than deleted — it is
    still the right assertion, pointed the other way. `routes_guide`
    turns this empty set into a redirect to `/about`; the resolver
    itself stays pure.
    """
    viewer = _viewer(db)

    assert visible_audiences(db, viewer) == frozenset()
    assert visible_sections(db, viewer) == frozenset()


def test_an_operator_sees_the_operator_walkthrough_and_not_the_role_cards(
    db: Session,
) -> None:
    viewer = _viewer(db, operator=True)

    assert visible_audiences(db, viewer) == frozenset({OPERATOR})
    assert "create_and_set_up" in visible_sections(db, viewer)
    assert "for_reviewers" not in visible_sections(db, viewer)


def test_a_sys_admin_counts_as_an_operator(db: Session) -> None:
    """Mirrors `require_operator`, where sys-admin implies operator (F4).

    Restating that rule instead of deriving it would let the Guide describe
    a different set of people from the one that can reach the pages it
    documents.
    """
    viewer = _viewer(db, email="admin@example.edu")
    viewer.is_sys_admin = True
    db.flush()

    assert OPERATOR in visible_audiences(db, viewer)


def test_roles_come_from_roster_rows_in_any_session(
    client: TestClient, db: Session
) -> None:
    """Held-anywhere, not held-here: the Guide is one page for the whole
    workspace, so a reviewer on one session is a reviewer while reading it."""
    review_session = _make_session(client, db, code="guide-roles")
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Rev",
            email="rev@example.edu",
            status="active",
        )
    )
    db.flush()

    viewer = _viewer(db, email="rev@example.edu")

    assert visible_audiences(db, viewer) == frozenset({REVIEWER})
    assert "for_reviewers" in visible_sections(db, viewer)
    assert "create_and_set_up" not in visible_sections(db, viewer)


def test_an_operator_who_is_also_a_reviewer_sees_both(
    client: TestClient, db: Session
) -> None:
    """The roles are not exclusive, and an operator reviewing on someone
    else's session is the ordinary case, not an edge one."""
    review_session = _make_session(client, db, code="guide-both")
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Both",
            email="both@example.edu",
            status="active",
        )
    )
    db.flush()

    viewer = _viewer(db, email="both@example.edu", operator=True)

    assert visible_audiences(db, viewer) == frozenset({OPERATOR, REVIEWER})


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
        routes_guide, "visible_sections", lambda db, user: frozenset({"for_observers"})
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


# ── 19F PR 3 — the Guide closes to a viewer who resolves nothing ──────


def test_guide_bounces_a_no_audience_viewer_to_about(
    client: TestClient, db: Session, make_client, bob
) -> None:
    """Decision 6. `/about` rather than a 404: the chrome offers this
    link to everyone, and refusing a link the app itself rendered is a
    worse answer than moving the reader somewhere useful. `/about` has
    been the "signed in but no access" landing since 18R Item 6."""
    monkey = make_client(bob)  # bob is on the operator allowlist...
    assert monkey.get("/guide", follow_redirects=False).status_code == 200

    stranger = make_client(
        AuthenticatedUser(
            principal_id="nul-oid", email="nul@example.edu",
            name="Nul", provider="aad",
        )
    )
    response = stranger.get("/guide", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/about"


def test_an_ungranted_reviewee_is_bounced_like_a_stranger(
    client: TestClient, db: Session, make_client, grant_reviewee_visibility
) -> None:
    """The case that forced `disclosable_roles` to become grant-aware
    before this rung could land.

    Without it a reviewee granted nothing still resolves the `reviewee`
    audience, reaches `/guide`, and is handed the *For reviewees* card —
    the disclosure 19F closes on `/me` and `/results`, relocated one
    page over rather than removed.
    """
    client.post(
        "/operator/sessions",
        data={"name": "S", "code": "guide-grant", "description": ""},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "guide-grant")
    ).scalar_one()
    db.add(
        Reviewee(
            session_id=review_session.id,
            name="Dana",
            email_or_identifier="dana@example.edu",
        )
    )
    db.commit()
    dana = make_client(
        AuthenticatedUser(
            principal_id="dana-oid", email="dana@example.edu",
            name="Dana", provider="aad",
        )
    )

    # Ungranted: bounced, exactly as a stranger is.
    assert dana.get("/guide", follow_redirects=False).status_code == 303

    # Granted: the Guide opens, and shows the reviewee card.
    grant_reviewee_visibility(review_session)
    body = dana.get("/guide", follow_redirects=False)
    assert body.status_code == 200
    assert "for_reviewees" in body.text or "For reviewees" in body.text


def test_the_chrome_hides_the_guide_link_for_a_no_audience_viewer(
    client: TestClient, db: Session, make_client, bob
) -> None:
    """Asserted on ``/about``, which is the page that matters, and the
    first draft of this test got that wrong.

    It looked at ``/me`` — but participant surfaces override
    ``top_bar`` with ``reviewer/_top_bar.html``, a lighter chrome that
    carries **no Guide link at all**. So a stranger never meets the link
    there, and gating ``base.html`` alone would have changed nothing a
    stranger sees.

    ``/about`` is where it bites: it uses the default chrome, and it is
    where ``/guide`` bounces such a viewer *to*. Left ungated, the
    bounce would hand them a link straight back to the page that
    bounced them.
    """
    operator_body = make_client(bob).get("/about").text
    assert 'class="chrome-link" href="/guide' in operator_body

    stranger_body = make_client(
        AuthenticatedUser(
            principal_id="nul2-oid", email="nul2@example.edu",
            name="Nul", provider="aad",
        )
    ).get("/about").text
    assert 'class="chrome-link" href="/guide' not in stranger_body
    # And the identity line renders a name — /about depended on the
    # header-derived user until 19F PR 3, so this read "Signed in as "
    # with nothing after it, the same defect 19E rung 7 fixed on /guide.
    assert "Signed in as Nul" in stranger_body


def test_the_participant_chrome_offers_no_guide_link_to_anyone(
    client: TestClient, db: Session, make_client, bob
) -> None:
    """Pins the fact the test above was written against.

    ``reviewer/_top_bar.html`` offers "My Reviews", "About" and "Sign
    out" — never the Guide. If a Guide link is ever added there it must
    carry the same condition as the one in ``base.html``, and this test
    is what will say so.
    """
    body = make_client(bob).get("/me").text
    assert 'href="/about' in body
    assert 'href="/guide' not in body
