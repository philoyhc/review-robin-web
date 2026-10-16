"""Revisiting a reviewer POST address with a GET lands on its page
(participant audit M10, `guide/archive/participant_surface_check.md`).

After a refused Submit, or a Save that re-rendered with errors, the
address bar holds the POST's URL. Pressing Enter there, or signing in
again, used to answer 405 ("Something went wrong") or 422 ("Bad
request")."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def test_a_get_on_save_returns_to_its_page(client: TestClient) -> None:
    resp = client.get("/me/sessions/7/2/save", follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == "/me/sessions/7/2"


@pytest.mark.parametrize(
    ("path", "location"),
    [
        ("/me/sessions/7/submit?page=3", "/me/sessions/7/3"),
        ("/me/sessions/7/submit", "/me/sessions/7/1"),
        # Only a number reaches the Location.
        ("/me/sessions/7/submit?page=//evil.example", "/me/sessions/7/1"),
        ("/me/sessions/7/recall", "/me/sessions/7/summary"),
        ("/me/sessions/7/clear", "/me/sessions/7"),
    ],
)
def test_a_get_on_a_session_action_returns_to_its_page(
    client: TestClient, path: str, location: str
) -> None:
    resp = client.get(path, follow_redirects=False)
    assert resp.status_code == 303
    assert resp.headers["location"] == location
