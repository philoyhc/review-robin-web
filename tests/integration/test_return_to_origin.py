"""End-to-end coverage for the return-to-origin affordance on About + /auth/me/debug
and the chrome user-menu About link that populates ``return_to`` (Segment 11D, PR A)."""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession


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
    # No self-referencing About link in chrome when already on /about.
    assert 'class="chrome-link"' not in body
