"""Role-aware landing redirects (Segment 18R Item 6).

``/`` routes by role: operators + sys-admins → the session lobby,
everyone else → the ``/me`` participant dashboard. ``/operator`` (and
``/operator/``) redirect to the lobby unconditionally.
"""

import pytest
from fastapi.testclient import TestClient

from app.auth.identity import AuthenticatedUser
from app.config import settings


def test_root_redirects_operator_to_lobby(client: TestClient) -> None:
    # ``client`` is signed in as alice, seeded into OPERATOR_EMAILS.
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/operator/sessions"


def test_root_redirects_participant_to_me(make_client) -> None:
    # An identity not in the operator allowlist bootstraps as a
    # non-operator, non-sys-admin → the /me dashboard.
    rae = AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )
    resp = make_client(rae).get("/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/me"


def test_operator_bare_redirects_to_lobby(client: TestClient) -> None:
    for path in ("/operator", "/operator/"):
        resp = client.get(path, follow_redirects=False)
        assert resp.status_code == 302, path
        assert resp.headers["location"] == "/operator/sessions", path


def test_operator_bare_lands_a_non_operator_on_the_user_lobby(make_client) -> None:
    # Segment 20N: bare /operator lands by role, as / does, so a
    # non-operator goes straight to the User Lobby, not through the
    # Operator Lobby's gate and its notice.
    rae = AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )
    for path in ("/operator", "/operator/"):
        resp = make_client(rae).get(path, follow_redirects=False)
        assert resp.status_code == 302, path
        assert resp.headers["location"] == "/me", path


# --- /about absorbed the retired /request-access access-help role -----------


def test_request_access_route_is_retired(client: TestClient) -> None:
    resp = client.get("/request-access", follow_redirects=False)
    assert resp.status_code == 404


def test_about_shows_identity_and_my_reviews(make_client) -> None:
    rae = AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )
    body = make_client(rae).get("/about").text
    assert "rae@example.edu" in body  # signed-in identity
    assert 'href="/me"' in body  # link to their reviews
    assert "Access" in body  # the access-help card


def test_about_shows_contact_mailto_when_configured(
    make_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "operator_contact_email", "admin@example.edu")
    rae = AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )
    body = make_client(rae).get("/about").text
    assert "mailto:admin@example.edu" in body


def test_me_chrome_carries_about_link(make_client) -> None:
    # The participant (/me) chrome now includes the About link, same as
    # the operator chrome's top-right menu.
    rae = AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )
    body = make_client(rae).get("/me").text
    assert 'href="/about?return_to' in body


# --- Segment 20N: the Operator Lobby and the User Lobby ---------------------


def test_the_operator_lobby_is_named_so(client: TestClient) -> None:
    body = client.get("/operator/sessions").text
    assert "<title>Operator Lobby — Review Robin Web</title>" in body
    assert "<h1>Operator Lobby</h1>" in body
    assert 'aria-current="page">Operator Lobby <span aria-hidden="true">✓</span>' in body
    assert "data-your-reviews>User Lobby</a>" in body  # the operator's switcher offers both


def test_the_user_lobby_is_named_so(client: TestClient) -> None:
    body = client.get("/me").text
    assert "<title>User Lobby — Review Robin Web</title>" in body
    assert "<h1>User Lobby</h1>" in body
