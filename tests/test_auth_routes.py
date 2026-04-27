from __future__ import annotations

import base64
import json

from fastapi import Request
from fastapi.testclient import TestClient

from app.auth.identity import AuthenticatedUser, get_current_user, resolve_current_user
from app.config import Settings
from app.main import app


def test_me_returns_identity_from_easy_auth_headers() -> None:
    client = TestClient(app)

    response = client.get(
        "/me",
        headers={
            "X-MS-CLIENT-PRINCIPAL-NAME": "alice@example.edu",
            "X-MS-CLIENT-PRINCIPAL-ID": "principal-123",
            "X-MS-CLIENT-PRINCIPAL-IDP": "aad",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "principal_id": "principal-123",
        "email": "alice@example.edu",
        "name": None,
        "provider": "aad",
        "is_fake": False,
    }


def test_me_returns_401_when_unauthenticated_and_fake_auth_disabled() -> None:
    real_settings = Settings(allow_fake_auth=False)

    def override_get_current_user(request: Request) -> AuthenticatedUser:
        return resolve_current_user(request, real_settings)

    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        client = TestClient(app)
        response = client.get("/me")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 401


def test_me_returns_fake_identity_when_fake_auth_enabled() -> None:
    fake_settings = Settings(allow_fake_auth=True)

    def override_get_current_user(request: Request) -> AuthenticatedUser:
        return resolve_current_user(request, fake_settings)

    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        client = TestClient(app)
        response = client.get("/me")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    body = response.json()
    assert body["is_fake"] is True
    assert body["provider"] == "fake"
    assert body["email"] == "operator@example.edu"


def _encode_principal(payload: dict) -> str:
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def test_me_debug_renders_html_with_identity_and_claims() -> None:
    client = TestClient(app)
    rich = _encode_principal(
        {
            "auth_typ": "aad",
            "claims": [
                {
                    "typ": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
                    "val": "alice@example.edu",
                },
                {"typ": "name", "val": "Alice Example"},
                {
                    "typ": "http://schemas.microsoft.com/identity/claims/objectidentifier",
                    "val": "oid-456",
                },
            ],
        }
    )

    response = client.get(
        "/me/debug",
        headers={"X-MS-CLIENT-PRINCIPAL": rich},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.text
    assert "Alice Example" in body
    assert "alice@example.edu" in body
    assert "oid-456" in body
    assert 'href="/.auth/logout"' in body


def test_me_debug_returns_401_when_unauthenticated() -> None:
    real_settings = Settings(allow_fake_auth=False)

    def override_get_current_user(request: Request) -> AuthenticatedUser:
        return resolve_current_user(request, real_settings)

    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        client = TestClient(app)
        response = client.get("/me/debug")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 401


def test_me_debug_renders_with_fake_auth_and_no_claims() -> None:
    fake_settings = Settings(allow_fake_auth=True)

    def override_get_current_user(request: Request) -> AuthenticatedUser:
        return resolve_current_user(request, fake_settings)

    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        client = TestClient(app)
        response = client.get("/me/debug")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert response.status_code == 200
    body = response.text
    assert "fake auth" in body.lower()
    assert "Local Operator" in body
    assert "No claims found" in body
