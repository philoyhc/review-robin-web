"""Who may use a Utilities tool: the platform super-admin alone, for every
tool so far (`utilityapps/spec/utilities.md` "Pages"). Anyone else signed
in gets a plain `403`; nobody signed in, the `401` `resolve_identity`
raises."""

from __future__ import annotations

from fastapi import HTTPException
from starlette.requests import Request

from cordware.identity import resolve_identity


def require_super_admin(request: Request) -> None:
    identity = resolve_identity(request)  # 401 with no identity
    if not identity.is_super_admin:
        raise HTTPException(status_code=403)
