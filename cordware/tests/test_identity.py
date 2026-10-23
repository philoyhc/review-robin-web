"""Cordware's identity: the Easy Auth parser, the fake user, the switches
and the guard (segment 21C rung C1, `guide/archive/segment_21C_shared_identity.md`).
"""

from __future__ import annotations

import base64
import inspect
import json
import logging

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

from cordware import identity as identity_module
from cordware.identity import (
    Identity,
    app_env,
    fake_auth,
    get_identity,
    is_local,
    is_super_admin_email,
    missing_header_count,
    resolve_identity,
    super_admin_configured,
    super_admin_emails,
)
from cordware.main import FakeAuthRefused, create_app
from cordware.settings import IdentitySettings, identity_settings


def _request(headers: dict[str, str] | None = None) -> Request:
    raw = []
    for key, value in (headers or {}).items():
        raw.append((key.lower().encode("latin-1"), value.encode("latin-1")))
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/auth/me",
        "headers": raw,
    }
    return Request(scope)


def _settings(allow_fake_auth: bool = False) -> IdentitySettings:
    return IdentitySettings(allow_fake_auth=allow_fake_auth)


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

    user = resolve_identity(request, _settings())

    assert user == Identity(
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

    user = resolve_identity(request, _settings())

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

    user = resolve_identity(request, _settings())

    assert user.email == "bob@example.edu"
    assert user.name == "Bob Example"
    assert user.principal_id == "oid-456"
    assert user.provider == "aad"
    assert user.is_fake is False


_EMAILADDRESS = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress"
_NAME_URI = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name"
_OID_URI = "http://schemas.microsoft.com/identity/claims/objectidentifier"
_RICH_CLAIMS = [
    {"typ": "email", "val": "plain@example.edu"},
    {"typ": "preferred_username", "val": "upn@example.edu"},
    {"typ": _EMAILADDRESS, "val": "primary@example.edu"},
    {"typ": _NAME_URI, "val": "Uri Name"},
    {"typ": "name", "val": "Short Name"},
    {"typ": "sub", "val": "sub-1"},
    {"typ": "oid", "val": "oid-1"},
    {"typ": _OID_URI, "val": "oid-uri-1"},
]


@pytest.mark.parametrize(
    "claims",
    [_RICH_CLAIMS, list(reversed(_RICH_CLAIMS))],
    ids=["lowest-priority-first", "highest-priority-first"],
)
def test_claim_priority_is_honored_regardless_of_token_order(
    claims: list[dict[str, str]],
) -> None:
    """Findings P5: each slot takes the first claim type its priority
    names, not the first the token happens to list."""
    rich = _encode_principal({"auth_typ": "aad", "claims": claims})

    user = resolve_identity(
        _request({"X-MS-CLIENT-PRINCIPAL": rich}), _settings()
    )

    assert user.email == "primary@example.edu"
    assert user.name == "Short Name"
    assert user.principal_id == "oid-uri-1"


def test_claim_priority_falls_through_to_the_next_type() -> None:
    """An absent or empty higher-priority claim yields to the next."""
    rich = _encode_principal(
        {
            "claims": [
                {"typ": "email", "val": "plain@example.edu"},
                {"typ": _EMAILADDRESS, "val": ""},
                {"typ": "preferred_username", "val": "upn@example.edu"},
                {"typ": "sub", "val": "sub-1"},
                {"typ": _NAME_URI, "val": "Uri Name"},
            ]
        }
    )

    user = resolve_identity(
        _request({"X-MS-CLIENT-PRINCIPAL": rich}), _settings()
    )

    assert user.email == "upn@example.edu"
    assert user.name == "Uri Name"
    assert user.principal_id == "sub-1"


def test_a_whitespace_only_email_claim_yields_to_the_next() -> None:
    """Findings 2026-10-22 P1: an email claim counts only when non-empty
    after strip, so a blank one no longer hides a valid fallback."""
    rich = _encode_principal(
        {
            "claims": [
                {"typ": _EMAILADDRESS, "val": "   "},
                {"typ": "preferred_username", "val": "\t"},
                {"typ": "preferred_username", "val": "upn@example.edu"},
                {"typ": "email", "val": "plain@example.edu"},
            ]
        }
    )

    user = resolve_identity(
        _request({"X-MS-CLIENT-PRINCIPAL": rich}), _settings()
    )

    assert user.email == "upn@example.edu"


def test_whitespace_only_email_claims_leave_no_email() -> None:
    """With every email claim blank after strip the identity carries no
    email, which RRW's `get_or_create_user` answers 401."""
    rich = _encode_principal(
        {
            "claims": [
                {"typ": _EMAILADDRESS, "val": " "},
                {"typ": "preferred_username", "val": "  "},
                {"typ": "email", "val": "\n"},
                {"typ": "name", "val": "Blank Email"},
            ]
        }
    )

    user = resolve_identity(
        _request({"X-MS-CLIENT-PRINCIPAL": rich}), _settings()
    )

    assert user.email is None
    assert user.name == "Blank Email"


def test_a_whitespace_only_object_id_yields_to_the_next() -> None:
    """Findings 2026-10-22 P3: a blank object id, as a claim or as the
    ``X-MS-CLIENT-PRINCIPAL-ID`` header, no longer hides a valid ``oid``."""
    rich = _encode_principal(
        {
            "claims": [
                {"typ": _OID_URI, "val": "  "},
                {"typ": "oid", "val": "oid-1"},
                {"typ": "sub", "val": "sub-1"},
            ]
        }
    )

    for headers in (
        {"X-MS-CLIENT-PRINCIPAL": rich},
        {"X-MS-CLIENT-PRINCIPAL": rich, "X-MS-CLIENT-PRINCIPAL-ID": " "},
    ):
        user = resolve_identity(_request(headers), _settings())
        assert user.principal_id == "oid-1"


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

    user = resolve_identity(request, _settings())

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

    user = resolve_identity(request, _settings())

    assert user.email == "dora@example.edu"
    assert user.principal_id == "principal-789"


def test_no_headers_and_fake_auth_disabled_raises_401() -> None:
    request = _request()

    with pytest.raises(HTTPException) as excinfo:
        resolve_identity(request, _settings(allow_fake_auth=False))

    assert excinfo.value.status_code == 401


def test_no_headers_and_fake_auth_enabled_returns_fake_user() -> None:
    request = _request()

    user = resolve_identity(request, _settings(allow_fake_auth=True))

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

    user = resolve_identity(request, _settings(allow_fake_auth=True))

    assert user.is_fake is False
    assert user.email == "real@example.edu"


def _events(caplog: pytest.LogCaptureFixture, event: str) -> list[logging.LogRecord]:
    return [r for r in caplog.records if getattr(r, "event", None) == event]


def test_get_identity_takes_the_request_alone() -> None:
    """FastAPI reads every parameter of a dependency from the request, so
    a settings parameter here would let a caller post fake auth on."""
    assert list(inspect.signature(get_identity).parameters) == ["request"]


def test_get_identity_reads_the_shared_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "allow_fake_auth", True)
    assert get_identity(_request()).is_fake is True
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    with pytest.raises(HTTPException):
        get_identity(_request())


@pytest.mark.parametrize(
    ("name", "value", "field", "expected"),
    [
        ("APP_ENV", "production", "app_env", "production"),
        ("ALLOW_FAKE_AUTH", "true", "allow_fake_auth", True),
        ("FAKE_AUTH_PRINCIPAL_ID", "pid-9", "fake_auth_principal_id", "pid-9"),
        ("FAKE_AUTH_EMAIL", "tester@example.edu", "fake_auth_email", "tester@example.edu"),
        ("FAKE_AUTH_NAME", "Test Er", "fake_auth_name", "Test Er"),
        (
            "SUPER_ADMIN_EMAILS",
            " boss@example.edu, ,Root@Example.edu ",
            "super_admin_emails",
            ["boss@example.edu", "Root@Example.edu"],
        ),
        ("FAKE_AUTH_SUPER_ADMIN", "false", "fake_auth_super_admin", False),
    ],
)
def test_each_switch_is_set_per_run(
    monkeypatch: pytest.MonkeyPatch, name: str, value: str, field: str, expected: object
) -> None:
    """A shell value (`$env:NAME=…` / `export NAME=…`) overrides `.env`."""
    monkeypatch.setenv(name, value)
    assert getattr(IdentitySettings(), field) == expected


def test_host_level_reads() -> None:
    local = IdentitySettings(app_env="local", allow_fake_auth=True, fake_auth_email="me@x.edu")
    deployed = IdentitySettings(app_env="production", allow_fake_auth=False)
    assert fake_auth(local) == identity_module.FakeAuth(enabled=True, email="me@x.edu")
    assert fake_auth(deployed).enabled is False
    assert (app_env(local), is_local(local)) == ("local", True)
    assert (app_env(deployed), is_local(deployed)) == ("production", False)


def test_the_guard_refuses_fake_auth_outside_local(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(identity_settings, "allow_fake_auth", True)
    monkeypatch.setattr(identity_settings, "app_env", "production")
    with caplog.at_level(logging.INFO, logger="cordware"):
        with pytest.raises(FakeAuthRefused, match="APP_ENV='production'"):
            create_app(apps=())
    (refused,) = _events(caplog, "identity.fake_auth_refused")
    assert refused.levelno == logging.ERROR
    assert _events(caplog, "identity.fake_auth_enabled") == []


def test_the_guard_refuses_before_any_application_is_built(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cordware.main import AppEntry

    monkeypatch.setattr(identity_settings, "allow_fake_auth", True)
    monkeypatch.setattr(identity_settings, "app_env", "staging")
    registry = {"boom": AppEntry(path="/boom", factory=f"{__name__}:_never_built", logger="boom")}
    with pytest.raises(FakeAuthRefused):
        create_app(apps=("boom",), registry=registry)


def _never_built() -> None:
    raise AssertionError("the guard must refuse before any factory runs")


def test_the_guard_allows_fake_auth_at_local_and_warns(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(identity_settings, "allow_fake_auth", True)
    monkeypatch.setattr(identity_settings, "app_env", "local")
    with caplog.at_level(logging.INFO, logger="cordware"):
        create_app(apps=())
    (enabled,) = _events(caplog, "identity.fake_auth_enabled")
    assert enabled.levelno == logging.WARNING


def test_the_guard_is_silent_with_fake_auth_off(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    monkeypatch.setattr(identity_settings, "app_env", "production")
    with caplog.at_level(logging.INFO, logger="cordware"):
        create_app(apps=())
    assert _events(caplog, "identity.fake_auth_refused") == []
    assert _events(caplog, "identity.fake_auth_enabled") == []


def test_a_malformed_header_is_logged_every_time_without_its_contents(
    caplog: pytest.LogCaptureFixture,
) -> None:
    request = _request(
        {"X-MS-CLIENT-PRINCIPAL": "!!secret-ish!!", "X-MS-CLIENT-PRINCIPAL-ID": "p-1"}
    )
    with caplog.at_level(logging.WARNING, logger="cordware.identity"):
        resolve_identity(request, _settings())
        resolve_identity(request, _settings())
    assert len(_events(caplog, "identity.header_malformed")) == 2
    assert "secret-ish" not in caplog.text


def test_a_missing_header_is_logged_once_and_counted(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(identity_module, "_missing_headers", 0)
    with caplog.at_level(logging.WARNING, logger="cordware.identity"):
        for _ in range(3):
            with pytest.raises(HTTPException):
                resolve_identity(_request(), _settings())
    assert len(_events(caplog, "identity.headers_missing")) == 1
    assert missing_header_count() == 3


def test_the_stop_line_carries_the_missing_header_count(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setattr(identity_module, "_missing_headers", 4)
    with caplog.at_level(logging.INFO, logger="cordware"):
        with TestClient(create_app(apps=())):
            pass
    (stopping,) = _events(caplog, "host.stopping")
    assert stopping.missing_identity_headers == 4


@pytest.mark.parametrize("fake", [False, True], ids=["fake-off", "fake-on"])
@pytest.mark.parametrize("listed", [[], ["Boss@Example.edu"]], ids=["empty", "listed"])
def test_super_admin_reads(fake: bool, listed: list[str]) -> None:
    """The flag, the predicate and `super_admin_configured` with an empty
    and a non-empty list, fake auth on and off (21C C3)."""
    s = IdentitySettings(super_admin_emails=listed, allow_fake_auth=fake)
    expected = tuple(e.lower() for e in listed) + (("operator@example.edu",) if fake else ())
    assert super_admin_emails(s) == expected
    assert super_admin_configured(s) is bool(expected)
    assert is_super_admin_email(" boss@EXAMPLE.edu ", s) is bool(listed)
    assert is_super_admin_email("operator@example.edu", s) is fake
    assert is_super_admin_email(None, s) is False
    assert is_super_admin_email("  ", s) is False


def test_fake_auth_super_admin_off_drops_only_the_fold_in() -> None:
    s = IdentitySettings(
        super_admin_emails=["boss@example.edu"], allow_fake_auth=True, fake_auth_super_admin=False
    )
    assert super_admin_emails(s) == ("boss@example.edu",)


def test_identity_super_admin_is_computed_from_the_shared_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    identity = Identity(principal_id="p", email="boss@example.edu", name=None)
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    monkeypatch.setattr(identity_settings, "super_admin_emails", [])
    assert (identity.is_super_admin, identity.super_admin_configured) == (False, False)
    monkeypatch.setattr(identity_settings, "super_admin_emails", ["boss@example.edu"])
    assert (identity.is_super_admin, identity.super_admin_configured) == (True, True)


@pytest.mark.parametrize(
    ("env", "listed", "warned"),
    [("production", [], True), ("production", ["boss@example.edu"], False), ("local", [], False)],
)
def test_the_host_warns_on_no_super_admin_in_a_deployed_environment(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    env: str,
    listed: list[str],
    warned: bool,
) -> None:
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    monkeypatch.setattr(identity_settings, "app_env", env)
    monkeypatch.setattr(identity_settings, "super_admin_emails", listed)
    with caplog.at_level(logging.INFO, logger="cordware"):
        create_app(apps=())
    assert bool(_events(caplog, "super_admin.unconfigured")) is warned


def test_explicit_settings_carry_to_the_role_properties(monkeypatch: pytest.MonkeyPatch) -> None:
    """Codex on #3213: an identity resolved under passed-in settings reads
    its role flags from them, not from the host's."""
    monkeypatch.setattr(identity_settings, "allow_fake_auth", False)
    monkeypatch.setattr(identity_settings, "super_admin_emails", [])
    fake = resolve_identity(_request(), IdentitySettings(allow_fake_auth=True))
    assert (fake.is_super_admin, fake.super_admin_configured) == (True, True)
    listed = IdentitySettings(super_admin_emails=["boss@example.edu"])
    boss = resolve_identity(_request({"X-MS-CLIENT-PRINCIPAL-NAME": "boss@example.edu"}), listed)
    assert boss.is_super_admin is True
    # The dependency's identity reads the host's settings.
    assert get_identity(_request({"X-MS-CLIENT-PRINCIPAL-NAME": "boss@example.edu"})).is_super_admin is False
    assert boss == Identity(principal_id=None, email="boss@example.edu", name=None)


@pytest.mark.parametrize(
    "raw",
    [
        b"\x80abc",
        b'{"claims": "\xc3("}',
        b"[1, 2]",
        b"not json",
        b'{"x": ' + b"1" * 5000 + b"}",
        b"[" * 10000,
    ],
    ids=["non-utf8", "non-utf8-in-json", "not-an-object", "not-json", "long-int", "deep"],
)
def test_a_decodable_but_malformed_principal_is_logged_not_raised(
    raw: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    """Codex on #3214: base64 of non-UTF-8 bytes raised a 500."""
    header = base64.b64encode(raw).decode("ascii")
    request = _request({"X-MS-CLIENT-PRINCIPAL": header, "X-MS-CLIENT-PRINCIPAL-ID": "p-2"})
    with caplog.at_level(logging.WARNING, logger="cordware.identity"):
        identity = resolve_identity(request, _settings())
    assert identity.principal_id == "p-2"
    assert len(_events(caplog, "identity.header_malformed")) == 1


def test_only_a_string_names_the_provider() -> None:
    rich = _encode_principal({"auth_typ": {"a": 1}, "identityProvider": "aad", "claims": []})
    identity = resolve_identity(_request({"X-MS-CLIENT-PRINCIPAL": rich}), _settings())
    assert identity.provider == "aad"
