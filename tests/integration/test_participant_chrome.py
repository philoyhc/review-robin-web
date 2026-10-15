"""The operator chrome as a participant sees it on the shared pages
(About, Guide, Sign-in details): participant audit M8,
`guide/participant_surface_check.md`."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.config import settings
from app.db.models import Reviewer, ReviewSession

_SETTINGS_LINK = 'class="chrome-link" href="/operator/settings'


def _participant(make_client) -> TestClient:
    return make_client(
        AuthenticatedUser(
            principal_id="pat-oid", email="pat@example.edu",
            name="Pat Participant", provider="aad",
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
    db.add(
        Reviewer(session_id=review_session.id, name="Pat", email="pat@example.edu")
    )
    db.commit()
    return review_session


def test_a_participant_is_not_offered_the_operator_settings_link(
    make_client,
) -> None:
    """Settings sits behind `require_operator`; a participant who
    followed the link was bounced to /me without a word."""
    body = _participant(make_client).get("/about").text
    assert "Signed in as Pat Participant" in body
    assert _SETTINGS_LINK not in body


def test_an_operator_still_gets_the_settings_link(client: TestClient) -> None:
    assert _SETTINGS_LINK in client.get("/about").text


def test_the_guide_shows_the_app_version(
    client: TestClient, db: Session, make_client
) -> None:
    """The Guide's template environment never set `app_version`, so the
    chrome read "(version )"."""
    _seed_reviewer_session(client, db)
    body = _participant(make_client).get("/guide").text
    assert f"(version {settings.app_version})" in body
    assert "(version )" not in body


def test_sign_in_details_names_the_viewer(make_client) -> None:
    """The page renders from the header identity, which had no
    `display_label`, so the chrome read "Signed in as " and nothing."""
    body = _participant(make_client).get("/auth/me/debug").text
    assert "Signed in as Pat Participant" in body
