"""The trusted identity Cordware supplies to every mounted application.

v0.8 §3, "Shared identity, application-specific permissions"; the
interface is segment 21C's (`guide/archive/segment_21C_shared_identity.md`
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
- `current_identity(request, settings=None)`: the same resolution, None
  instead of a 401, for a page that shows who is signed in.
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
from dataclasses import dataclass, field, replace
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
    # The account's tenant, UPN and primary email as Entra gives them,
    # each its own field: an application matching a roster on first sign-in
    # tries the UPN and the email separately, and binds on (tenant,
    # principal_id) after (`residentialapps/docs/
    # residentialapps_email_identity_matching.md`). `email` above stays the
    # one address RRW and the super-admin list read.
    tenant_id: str | None = None
    upn: str | None = None
    mail: str | None = None
    # The settings a caller passed to `resolve_identity` (tests), so the
    # role properties read the configuration the identity was resolved
    # under. None, as from the dependency, reads the host's. Not part of
    # equality: two resolutions of one principal are the same identity.
    resolved_with: IdentitySettings | None = field(default=None, compare=False, repr=False)

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
        return is_super_admin_email(self.email, self.resolved_with)

    @property
    def super_admin_configured(self) -> bool:
        return super_admin_configured(self.resolved_with)


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
    except (ValueError, RecursionError):
        # Not JSON, not text `json.loads` can decode, an integer past
        # Python's digit limit, or nesting past the recursion limit: all
        # malformed, none a 500 (Codex and a cold read, #3214).
        # `JSONDecodeError` and `UnicodeDecodeError` are `ValueError`s.
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _claim(
    payload: dict[str, Any], *types: str, blank_counts: bool = True
) -> str | None:
    """The value of the first of ``types`` the claim set carries, in
    the order ``types`` names them — not the token's own claim order.
    Within one type the token's first non-empty value wins. With
    ``blank_counts=False`` a whitespace-only value is skipped too, so
    the next value in that order is used (findings 2026-10-22 P1)."""
    claims = payload.get("claims")
    if not isinstance(claims, list):
        return None
    for typ in types:
        for claim in claims:
            if not isinstance(claim, dict) or claim.get("typ") != typ:
                continue
            value = claim.get("val")
            if isinstance(value, str) and (value if blank_counts else value.strip()):
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
    tenant_id: str | None = None
    upn: str | None = None
    mail: str | None = None
    # A whitespace-only id is no id, as for the email claim (P3): it
    # would hide the principal header's object id.
    principal_id: str | None = simple_id if simple_id and simple_id.strip() else None
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
                # A whitespace-only email would store `""` and hide a
                # valid fallback claim; it counts as no email (P1).
                blank_counts=False,
            )
            name = _claim(
                payload,
                "name",
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
            )
            tenant_id = _claim(
                payload,
                "http://schemas.microsoft.com/identity/claims/tenantid",
                "tid",
                blank_counts=False,
            )
            # Entra's v2 `preferred_username` is usually the UPN when no
            # `upn` claim is issued, though it may be another username;
            # it is never taken as the primary email, so `mail` does not
            # fall back to it. v1's `unique_name` is not read.
            upn = _claim(
                payload,
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/upn",
                "upn",
                "preferred_username",
                blank_counts=False,
            )
            mail = _claim(
                payload,
                "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
                "email",
                blank_counts=False,
            )
            principal_id = principal_id or _claim(
                payload,
                "http://schemas.microsoft.com/identity/claims/objectidentifier",
                "oid",
                "sub",
                # A blank object id would hide a valid ``oid`` (P3).
                blank_counts=False,
            )
            provider = provider or next(
                (
                    value
                    for value in (payload.get("auth_typ"), payload.get("identityProvider"))
                    if isinstance(value, str) and value
                ),
                None,
            )

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
        tenant_id=tenant_id,
        upn=upn,
        mail=mail,
    )


def _fake_identity(settings: IdentitySettings) -> Identity:
    return Identity(
        principal_id=settings.fake_auth_principal_id,
        email=settings.fake_auth_email,
        name=settings.fake_auth_name,
        provider="fake",
        is_fake=True,
        # A blank tenant is no tenant, as a blank claim is (P1/P3).
        tenant_id=settings.fake_auth_tenant_id.strip() or None,
        # Blank means "the fake email", so one setting serves the usual
        # case and either can differ to try an alias.
        upn=settings.fake_auth_upn.strip() or settings.fake_auth_email,
        mail=settings.fake_auth_mail.strip() or settings.fake_auth_email,
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
    identity = current_identity(request, settings)
    if identity is not None:
        return identity
    _note_missing_headers()
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


def get_identity(request: Request) -> Identity:
    return resolve_identity(request)


def current_identity(request: Request, settings: IdentitySettings | None = None) -> Identity | None:
    """The resolution `resolve_identity` runs, returning None where that
    refuses, for a page that shows who is signed in without requiring it
    (the host's landing page). None raises nothing, counts nothing and
    logs no `identity.headers_missing`; a malformed principal header is
    still logged, as on every request."""
    cfg = _settings(settings)
    identity = _identity_from_easy_auth_headers(request)
    if identity is None and cfg.allow_fake_auth:
        identity = _fake_identity(cfg)
    if identity is None or settings is None:
        return identity
    return replace(identity, resolved_with=settings)


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
