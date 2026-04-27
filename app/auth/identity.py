from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request, status

from app.config import Settings, settings as default_settings


@dataclass(frozen=True)
class AuthenticatedUser:
    principal_id: str | None
    email: str | None
    name: str | None
    provider: str | None = None
    is_fake: bool = False


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
    claims = payload.get("claims")
    if not isinstance(claims, list):
        return None
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        if claim.get("typ") in types:
            value = claim.get("val")
            if isinstance(value, str) and value:
                return value
    return None


def _user_from_easy_auth_headers(request: Request) -> AuthenticatedUser | None:
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
        if payload is not None:
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

    return AuthenticatedUser(
        principal_id=principal_id,
        email=email,
        name=name,
        provider=provider,
    )


def _fake_user(settings: Settings) -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id=settings.fake_auth_principal_id,
        email=settings.fake_auth_email,
        name=settings.fake_auth_name,
        provider="fake",
        is_fake=True,
    )


def resolve_current_user(
    request: Request,
    settings: Settings | None = None,
) -> AuthenticatedUser:
    cfg = settings if settings is not None else default_settings
    user = _user_from_easy_auth_headers(request)
    if user is not None:
        return user
    if cfg.allow_fake_auth:
        return _fake_user(cfg)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


def get_current_user(request: Request) -> AuthenticatedUser:
    return resolve_current_user(request)
