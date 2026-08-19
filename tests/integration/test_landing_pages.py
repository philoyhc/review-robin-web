"""Role-aware landing redirects (Segment 18R Item 6).

``/`` routes by role: operators + sys-admins → the session lobby,
everyone else → the ``/me`` participant dashboard. ``/operator`` (and
``/operator/``) redirect to the lobby unconditionally.
"""

from fastapi.testclient import TestClient

from app.auth.identity import AuthenticatedUser


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


def test_operator_bare_redirect_is_unguarded_for_non_operators(make_client) -> None:
    # The bare-/operator redirect fires for anyone; the lobby's own gate
    # then applies the bounce. So a non-operator gets the redirect, not a
    # 403/deny at /operator itself.
    rae = AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )
    resp = make_client(rae).get("/operator", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["location"] == "/operator/sessions"
