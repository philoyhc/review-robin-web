"""The chrome a participant sees on the shared pages (About, Guide,
Sign-in details): participant audit M8,
`guide/archive/participant_surface_check.md`. Since segment 20D every page
renders the one shared top bar, and its entries follow the viewer's roles
(`docs/header_chrome.md` §3–§4)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.config import settings
from app.db.models import Reviewer, ReviewSession

_SETTINGS_LINK = 'href="/operator/settings?return_to='
_VERSION = f"<small>version {settings.app_version}</small>"


def _participant(make_client) -> TestClient:
    return make_client(
        AuthenticatedUser(
            principal_id="pat-oid",
            email="pat@example.edu",
            name="Pat Participant",
            provider="aad",
        )
    )


def _seed_reviewer_session(client: TestClient, db: Session) -> ReviewSession:
    client.post(
        "/operator/sessions",
        data={"name": "Chrome Check", "code": "rrw-chrome"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "rrw-chrome")
    ).scalar_one()
    db.add(Reviewer(session_id=review_session.id, name="Pat", email="pat@example.edu"))
    db.commit()
    return review_session


def test_a_participant_is_not_offered_the_operator_settings_link(
    make_client,
) -> None:
    """Settings sits behind `require_operator`; a participant who
    followed the link was bounced to /me without a word."""
    body = _participant(make_client).get("/about").text
    assert "<strong>Pat Participant</strong>" in body
    assert _SETTINGS_LINK not in body


def test_an_operator_still_gets_the_settings_link(client: TestClient) -> None:
    assert _SETTINGS_LINK in client.get("/about").text


def test_the_guide_shows_the_app_version(client: TestClient, db: Session, make_client) -> None:
    """The Guide's template environment never set `app_version`, so the
    operator chrome read "(version )". The account menu now shows it
    beside About, for operators only (20D)."""
    body = client.get("/guide").text
    assert _VERSION in body
    assert "<small>version </small>" not in body


@pytest.mark.parametrize("path", ["/about", "/guide", "/auth/me/debug"])
def test_shared_pages_show_a_participant_their_own_top_bar(
    client: TestClient, db: Session, make_client, path: str
) -> None:
    """About, Guide and Sign-in details took the operator top bar for
    everyone (participant audit M8). A participant's bar offers Your
    reviews, no Sessions and no version (20D)."""
    _seed_reviewer_session(client, db)
    body = _participant(make_client).get(path).text
    assert 'class="tb-app">Review Robin' in body
    assert "data-your-reviews" in body
    assert 'href="/operator/sessions"' not in body
    assert "<small>version" not in body


@pytest.mark.parametrize("path", ["/about", "/guide", "/auth/me/debug"])
def test_shared_pages_keep_the_operator_top_bar_for_an_operator(
    client: TestClient, path: str
) -> None:
    """Sign-in details picks its bar from a looked-up row rather than
    the gate's, so it needs the row to exist: any page creates it."""
    client.get("/about")
    body = client.get(path).text
    assert 'href="/operator/sessions"' in body
    # About and Sign-in details omit the About entry, and the version
    # beside it with it (`docs/header_chrome.md` §4).
    if path == "/guide":
        assert _VERSION in body


def test_sign_in_details_names_the_viewer(make_client) -> None:
    """The page renders from the header identity, which had no
    `display_label`, so the chrome read "Signed in as " and nothing. The
    account menu names them now (20D)."""
    body = _participant(make_client).get("/auth/me/debug").text
    assert "<strong>Pat Participant</strong>" in body


def test_about_names_the_dashboard_your_reviews(client: TestClient) -> None:
    """One name for the dashboard (participant audit L1)."""
    body = client.get("/about").text
    assert '<a href="/me">Your reviews</a>' in body
    assert "My reviews" not in body


def test_sign_in_details_offers_none_of_the_account_entries(
    client: TestClient, monkeypatch
) -> None:
    """`docs/header_chrome.md` §4: no Settings, Admin, Guide or About on
    Sign-in details, for an operator and a sys admin too (20D close)."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    client.get("/about")
    body = client.get("/auth/me/debug").text
    for path in ("/operator/settings?", "/operator/sys-admin?", "/guide?", "/about?"):
        assert f'href="{path}return_to=' not in body, path
