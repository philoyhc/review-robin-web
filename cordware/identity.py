"""The trusted identity Cordware supplies to every mounted application.

v0.8 §3, "Shared identity, application-specific permissions"; the
interface is segment 21C's (`guide/segment_21C_shared_identity.md`
§ Decision). Cordware is the only reader of Azure Easy Auth's
`X-MS-CLIENT-PRINCIPAL*` headers, and the only source of the fake local
identity, which the host refuses outside `APP_ENV=local`
(`cordware.main.create_app`). Applications map the identity to their own
users and permissions; nothing here decides what anyone may do.

- `Identity`: who the request is from.
- `get_identity(request)`: the dependency. It takes the request and
  nothing else, because FastAPI reads every parameter of a dependency
  from the request: a settings parameter would become a request body.
- `resolve_identity(request, settings)`: the same resolution with the
  settings passed in, for tests. Never a dependency.
- `fake_auth()`, `app_env()`, `is_local()`, `is_super_admin_email()`,
  `super_admin_configured()`, `super_admin_emails()`: host-level reads,
  valid outside a request.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
import threading
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request, status

from cordware.settings import IdentitySettings, identity_settings

log = logging.getLogger("cordware.identity")


@dataclass(frozen=True)
class Identity:
    principal_id: str | None
    email: str | None
    name: str | None
    provider: str | None = None
    is_fake: bool = False

    @property
    def display_label(self) -> str:
        """The chrome's "Signed in as …" name, as an application's
        persisted user gives it, so a page rendered from the identity
        alone names the viewer too."""
        return self.name or self.email or ""

    @property
    def is_super_admin(self) -> bool:
        """Computed from the host-level predicate, never stored, so the
        flag, `is_super_admin_email` and `super_admin_configured` agree."""
        return is_super_admin_email(self.email)

    @property
    def super_admin_configured(self) -> bool:
        return super_admin_configured()


@dataclass(frozen=True)
class FakeAuth:
    """Whether fake auth is on, and the fake account's email."""

    enabled: bool
    email: str


def _settings(settings: IdentitySettings | None) -> IdentitySettings:
    return settings if settings is not None else identity_settings


def fake_auth(settings: IdentitySettings | None = None) -> FakeAuth:
    s = _settings(settings)
    return FakeAuth(enabled=s.allow_fake_auth, email=s.fake_auth_email)


def app_env(settings: IdentitySettings | None = None) -> str:
    return _settings(settings).app_env


def is_local(settings: IdentitySettings | None = None) -> bool:
    return app_env(settings) == "local"


def _normalize_email(email: str) -> str:
    # RRW's `normalize_email` rule: strip, then `str.lower` (deliberately
    # not casefold). Cordware cannot import an application, so it keeps
    # its own copy, and an RRW test pins the two equal.
    return email.strip().lower()


def super_admin_emails(settings: IdentitySettings | None = None) -> tuple[str, ...]:
    """The effective super-admin list, normalized: `SUPER_ADMIN_EMAILS`,
    plus the fake account's email while fake auth and
    `FAKE_AUTH_SUPER_ADMIN` are both on."""
    s = _settings(settings)
    emails = list(s.super_admin_emails)
    if s.allow_fake_auth and s.fake_auth_super_admin:
        emails.append(s.fake_auth_email)
    return tuple(dict.fromkeys(_normalize_email(e) for e in emails if e.strip()))


def super_admin_configured(settings: IdentitySettings | None = None) -> bool:
    """Whether the effective super-admin list is non-empty."""
    return bool(super_admin_emails(settings))


def is_super_admin_email(email: str | None, settings: IdentitySettings | None = None) -> bool:
    """Whether ``email`` is in the effective super-admin list. A missing
    or blank email never is."""
    if not email or not email.strip():
        return False
    return _normalize_email(email) in super_admin_emails(settings)


def _decode_client_principal(header_value: str) -> dict[str, Any] | None:
    try:
        decoded = base64.b64decode(header_value, validate=True)
    except (binascii.Error, ValueError):
        return None
    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _claim(payload: dict[str, Any], *types: str) -> str | None:
    """The value of the first of ``types`` the claim set carries, in
    the order ``types`` names them — not the token's own claim order.
    Within one type the token's first non-empty value wins."""
    claims = payload.get("claims")
    if not isinstance(claims, list):
        return None
    for typ in types:
        for claim in claims:
            if not isinstance(claim, dict) or claim.get("typ") != typ:
                continue
            value = claim.get("val")
            if isinstance(value, str) and value:
                return value
    return None


def _identity_from_easy_auth_headers(request: Request) -> Identity | None:
    headers = request.headers
    simple_name = headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
    simple_id = headers.get("X-MS-CLIENT-PRINCIPAL-ID")
    simple_idp = headers.get("X-MS-CLIENT-PRINCIPAL-IDP")
    rich = headers.get("X-MS-CLIENT-PRINCIPAL")

    if not (simple_name or simple_id or rich):
        return None
    email: str | None = None
    name: str | None = None
    principal_id: str | None = simple_id
    provider: str | None = simple_idp

    if rich:
        payload = _decode_client_principal(rich)
        if payload is None:
            # The fact, never the contents (v0.8 §3, host logging event 3).
            log.warning(
                "malformed Easy Auth principal header",
                extra={"event": "identity.header_malformed"},
            )
        else:
            email = _claim(
                payload,
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
                "preferred_username",
                "email",
            )
            name = _claim(
                payload,
                "name",
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
            )
            principal_id = principal_id or _claim(
                payload,
                "http://schemas.microsoft.com/identity/claims/objectidentifier",
                "oid",
                "sub",
            )
            provider = provider or payload.get("auth_typ") or payload.get("identityProvider")

    if simple_name and not email:
        if "@" in simple_name:
            email = simple_name
        else:
            name = name or simple_name

    return Identity(
        principal_id=principal_id,
        email=email,
        name=name,
        provider=provider,
    )


def _fake_identity(settings: IdentitySettings) -> Identity:
    return Identity(
        principal_id=settings.fake_auth_principal_id,
        email=settings.fake_auth_email,
        name=settings.fake_auth_name,
        provider="fake",
        is_fake=True,
    )


_missing_headers = 0
# `get_identity` is a plain function, so FastAPI runs it on a worker
# thread: the count and the once-only check share a lock.
_missing_headers_lock = threading.Lock()


def missing_header_count() -> int:
    """Requests this process refused for want of Easy Auth headers."""
    return _missing_headers


def _note_missing_headers() -> None:
    # Logged once per process, with the running count on the host's stop
    # line: with fake auth off, every unauthenticated probe is "missing"
    # (21C Open question 1, author 2026-10-21).
    global _missing_headers
    with _missing_headers_lock:
        _missing_headers += 1
        first = _missing_headers == 1
    if first:
        log.warning(
            "request without Easy Auth headers refused",
            extra={"event": "identity.headers_missing"},
        )


def resolve_identity(request: Request, settings: IdentitySettings | None = None) -> Identity:
    """Easy Auth headers when present, else the fake identity when fake
    auth is on, else a 401. Never a dependency: see the module docstring."""
    cfg = _settings(settings)
    identity = _identity_from_easy_auth_headers(request)
    if identity is not None:
        return identity
    if cfg.allow_fake_auth:
        return _fake_identity(cfg)
    _note_missing_headers()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


def get_identity(request: Request) -> Identity:
    return resolve_identity(request)


def decode_client_principal(request: Request) -> dict[str, Any] | None:
    rich = request.headers.get("X-MS-CLIENT-PRINCIPAL")
    if not rich:
        return None
    return _decode_client_principal(rich)


def extract_claims(request: Request) -> list[dict[str, str]]:
    payload = decode_client_principal(request)
    if payload is None:
        return []
    raw = payload.get("claims")
    if not isinstance(raw, list):
        return []
    claims: list[dict[str, str]] = []
    for claim in raw:
        if not isinstance(claim, dict):
            continue
        typ = claim.get("typ")
        val = claim.get("val")
        if isinstance(typ, str) and isinstance(val, str):
            claims.append({"typ": typ, "val": val})
    return claims
