from __future__ import annotations

import base64
import json

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.auth.identity import (
    AuthenticatedUser,
    resolve_current_user,
)
from app.config import Settings


def _request(headers: dict[str, str] | None = None) -> Request:
    raw = []
    for key, value in (headers or {}).items():
        raw.append((key.lower().encode("latin-1"), value.encode("latin-1")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/me",
        "headers": raw,
    }
    return Request(scope)


def _settings(allow_fake_auth: bool = False) -> Settings:
    return Settings(allow_fake_auth=allow_fake_auth)


def _encode_principal(payload: dict[str, object]) -> str:
    return base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")


def test_simple_easy_auth_headers_parse_to_user() -> None:
    request = _request(
        {
            "X-MS-CLIENT-PRINCIPAL-NAME": "alice@example.edu",
            "X-MS-CLIENT-PRINCIPAL-ID": "principal-123",
            "X-MS-CLIENT-PRINCIPAL-IDP": "aad",
        }
    )

    user = resolve_current_user(request, _settings())

    assert user == AuthenticatedUser(
        principal_id="principal-123",
        email="alice@example.edu",
        name=None,
        provider="aad",
        is_fake=False,
    )


def test_principal_name_without_at_is_treated_as_name() -> None:
    request = _request(
        {
            "X-MS-CLIENT-PRINCIPAL-NAME": "Alice Example",
            "X-MS-CLIENT-PRINCIPAL-ID": "principal-123",
            "X-MS-CLIENT-PRINCIPAL-IDP": "aad",
        }
    )

    user = resolve_current_user(request, _settings())

    assert user.email is None
    assert user.name == "Alice Example"
    assert user.provider == "aad"


def test_rich_client_principal_header_extracts_claims() -> None:
    rich = _encode_principal(
        {
            "auth_typ": "aad",
            "claims": [
                {
                    "typ": "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
                    "val": "bob@example.edu",
                },
                {"typ": "name", "val": "Bob Example"},
                {
                    "typ": "http://schemas.microsoft.com/identity/claims/objectidentifier",
                    "val": "oid-456",
                },
            ],
        }
    )
    request = _request({"X-MS-CLIENT-PRINCIPAL": rich})

    user = resolve_current_user(request, _settings())

    assert user.email == "bob@example.edu"
    assert user.name == "Bob Example"
    assert user.principal_id == "oid-456"
    assert user.provider == "aad"
    assert user.is_fake is False


def test_simple_id_overrides_rich_when_both_present() -> None:
    rich = _encode_principal(
        {
            "auth_typ": "aad",
            "claims": [
                {"typ": "name", "val": "Carol Example"},
                {"typ": "preferred_username", "val": "carol@example.edu"},
            ],
        }
    )
    request = _request(
        {
            "X-MS-CLIENT-PRINCIPAL": rich,
            "X-MS-CLIENT-PRINCIPAL-ID": "simple-id-wins",
            "X-MS-CLIENT-PRINCIPAL-IDP": "aad",
        }
    )

    user = resolve_current_user(request, _settings())

    assert user.principal_id == "simple-id-wins"
    assert user.email == "carol@example.edu"
    assert user.name == "Carol Example"


def test_malformed_rich_header_falls_back_gracefully() -> None:
    request = _request(
        {
            "X-MS-CLIENT-PRINCIPAL": "!!!not-base64!!!",
            "X-MS-CLIENT-PRINCIPAL-NAME": "dora@example.edu",
            "X-MS-CLIENT-PRINCIPAL-ID": "principal-789",
            "X-MS-CLIENT-PRINCIPAL-IDP": "aad",
        }
    )

    user = resolve_current_user(request, _settings())

    assert user.email == "dora@example.edu"
    assert user.principal_id == "principal-789"


def test_no_headers_and_fake_auth_disabled_raises_401() -> None:
    request = _request()

    with pytest.raises(HTTPException) as excinfo:
        resolve_current_user(request, _settings(allow_fake_auth=False))

    assert excinfo.value.status_code == 401


def test_no_headers_and_fake_auth_enabled_returns_fake_user() -> None:
    request = _request()

    user = resolve_current_user(request, _settings(allow_fake_auth=True))

    assert user.is_fake is True
    assert user.provider == "fake"
    assert user.email == "operator@example.edu"
    assert user.name == "Local Operator"
    assert user.principal_id == "local-dev"


def test_easy_auth_headers_take_precedence_over_fake_auth() -> None:
    request = _request(
        {
            "X-MS-CLIENT-PRINCIPAL-NAME": "real@example.edu",
            "X-MS-CLIENT-PRINCIPAL-ID": "real-id",
            "X-MS-CLIENT-PRINCIPAL-IDP": "aad",
        }
    )

    user = resolve_current_user(request, _settings(allow_fake_auth=True))

    assert user.is_fake is False
    assert user.email == "real@example.edu"
