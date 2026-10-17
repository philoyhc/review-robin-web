"""End-to-end coverage for the return-to-origin affordance on About + /auth/me/debug
and the chrome user-menu About link that populates ``return_to`` (Segment 11D, PR A)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import ReviewSession, User


def _create_session(client: TestClient, db: Session, *, code: str = "rrw-rt") -> ReviewSession:
    client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_about_renders_default_back_link_without_return_to(
    client: TestClient,
) -> None:
    body = client.get("/about").text
    assert 'class="back-link"' in body
    assert 'href="/operator/sessions"' in body
    assert "Back to Sessions" in body


def test_about_renders_session_label_when_return_to_is_session_path(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db)
    body = client.get(
        f"/about?return_to=/operator/sessions/{session.id}"
    ).text
    assert f'href="/operator/sessions/{session.id}"' in body
    assert f"Back to {session.name}" in body


def test_about_falls_back_to_default_for_disallowed_return_to(
    client: TestClient,
) -> None:
    body = client.get("/about?return_to=https://evil.example.com").text
    assert "evil.example.com" not in body
    assert 'href="/operator/sessions"' in body
    assert "Back to Sessions" in body


def test_me_debug_renders_back_link(client: TestClient, db: Session) -> None:
    session = _create_session(client, db, code="rrw-md")
    body = client.get(
        f"/auth/me/debug?return_to=/operator/sessions/{session.id}"
    ).text
    assert 'class="back-link"' in body
    assert f"Back to {session.name}" in body


@pytest.mark.parametrize("page", ["/about", "/auth/me/debug"])
@pytest.mark.parametrize("shape", ["/me/sessions/{id}", "/operator/sessions/{id}"])
def test_a_stranger_is_not_told_a_session_name_by_the_back_link(
    client: TestClient, db: Session, make_client, page: str, shape: str
) -> None:
    """Participant audit P1: any signed-in user could read any session's
    name off a crafted ``return_to``. A viewer who cannot see the
    session gets the default link, as for an id that does not exist."""
    session = _create_session(client, db, code="rrw-secret")
    stranger = make_client(
        AuthenticatedUser(
            principal_id="eve-oid", email="eve@example.edu",
            name="Eve", provider="aad",
        )
    )
    body = stranger.get(f"{page}?return_to={shape.format(id=session.id)}").text
    assert session.name not in body
    # A participant's fallback is their own dashboard (audit M8). The
    # href and the label are asserted together: About carries a plain
    # "/me" link of its own.
    assert 'href="/me">&larr; Back to your reviews' in body


def test_me_debug_creates_no_user_row(
    client: TestClient, db: Session, make_client
) -> None:
    """The debug page looks the viewer up to decide a label; it never
    signs them in as a side effect. A real session makes the lookup
    decide a name as well as the fallback."""
    session = _create_session(client, db, code="rrw-norow")
    eve = make_client(
        AuthenticatedUser(
            principal_id="eve-oid", email="eve@example.edu",
            name="Eve", provider="aad",
        )
    )
    body = eve.get(f"/auth/me/debug?return_to=/me/sessions/{session.id}").text
    assert "Back to your reviews" in body
    assert db.execute(
        select(User).where(User.email == "eve@example.edu")
    ).first() is None


def test_me_debug_renders_when_the_user_lookup_fails(
    make_client, monkeypatch
) -> None:
    """Sign-in details is where a broken sign-in is diagnosed, so a
    failed lookup reads as no row instead of a 500."""
    from sqlalchemy.exc import OperationalError

    import app.web.routes_auth as routes_auth

    def broken(*_args: object, **_kwargs: object) -> None:
        raise OperationalError("SELECT 1", {}, Exception("database down"))

    monkeypatch.setattr(routes_auth, "find_user", broken)
    eve = make_client(
        AuthenticatedUser(
            principal_id="eve-oid", email="eve@example.edu",
            name="Eve", provider="aad",
        )
    )
    resp = eve.get("/auth/me/debug")
    assert resp.status_code == 200
    assert "Back to your reviews" in resp.text


def test_settings_does_not_name_another_operators_session(
    client: TestClient, db: Session, make_client, bob
) -> None:
    """A workspace operator reaches Settings, but a session they do not
    own stays unnamed in its back link."""
    session = _create_session(client, db, code="rrw-alices")
    body = make_client(bob).get(
        f"/operator/settings?return_to=/operator/sessions/{session.id}"
    ).text
    assert session.name not in body
    assert "Back to Sessions" in body


def test_chrome_about_link_carries_current_path_as_return_to(
    client: TestClient,
) -> None:
    body = client.get("/operator/sessions").text
    # The chrome About link is distinct from the chrome-app-identity anchor;
    # it carries the current path as ``return_to`` so the About page can
    # render a contextual back-link.
    assert (
        'class="chrome-link" href="/about?return_to=/operator/sessions">About</a>'
        in body
    )


def test_chrome_skips_about_link_on_about_page(client: TestClient) -> None:
    body = client.get("/about").text
    # No self-referencing About link in the chrome when already on /about.
    # (Other chrome links like Settings still render — /about now carries the
    # signed-in identity since 18R Item 6 — so check the About link itself.)
    assert 'href="/about?return_to' not in body
