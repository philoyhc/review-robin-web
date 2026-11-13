"""The placeholders' gate (segment AD1, item 2).

The pages show sample data and enforce no access rule yet. On a local run
(`APP_ENV=local`) they answer anyone; deployed, only the platform
super-admin, and 404 for everyone else, until the segments that wire them.
ApplyDesk is not shipped yet (Cordware's importer excludes `applydesk/`),
so it keeps no preview list of its own."""

from __future__ import annotations

from fastapi import HTTPException, Request

from cordware.identity import current_identity, is_local


def is_operator(request: Request) -> bool:
    """Whether the viewer lands on the Operator Lobby and sees it in the
    switcher (Cordware's lobbies, 2026-11-13). Until AD2 knows Apply Desk's
    operators: everyone on a local run, deployed only the super-admin, the
    one viewer a placeholder answers."""
    if is_local():
        return True
    identity = current_identity(request)
    return identity is not None and identity.is_super_admin


def placeholders_only(request: Request) -> None:
    if is_local():
        return
    identity = current_identity(request)
    if identity is None or not identity.is_super_admin:
        raise HTTPException(status_code=404)
