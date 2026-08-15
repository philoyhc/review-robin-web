"""18P PR G0 — the Rehydrate UI scaffold.

The lobby button + the ``/operator/sessions/rehydrate`` page with three
inert placeholder cards. No behaviour is wired yet (that lands in the
follow-up PRs); these tests pin the scaffold's shape.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_lobby_shows_rehydrate_button(client: TestClient) -> None:
    # The search-card button row (Cancel / Add new / Rehydrate / Go to
    # Archive) renders once the operator has a session; a bare lobby
    # shows the onboarding empty state instead.
    client.post(
        "/operator/sessions",
        data={"name": "Spring Reviews", "code": "spring-2026"},
        follow_redirects=False,
    )
    response = client.get("/operator/sessions")
    assert response.status_code == 200
    body = response.text
    assert 'href="/operator/sessions/rehydrate"' in body
    assert ">Rehydrate<" in body


def test_rehydrate_page_renders_scaffold(client: TestClient) -> None:
    response = client.get("/operator/sessions/rehydrate")
    assert response.status_code == 200
    body = response.text

    # All three cards present.
    assert "Rehydrate an extracted session" in body
    assert "Upload, validate, rehydrate" in body
    assert "Details &amp; validation" in body

    # A file input + both action buttons, all inert in the scaffold.
    assert 'type="file"' in body
    assert ">Validate</button>" in body
    assert ">Rehydrate</button>" in body
    assert 'aria-disabled="true"' in body

    # Breadcrumb back to the lobby.
    assert 'href="/operator/sessions"' in body
