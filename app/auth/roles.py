"""Config-derived role predicates (Segment 18S Item 1).

Super-admin is the top tier of the three-tier role model
(operator ⊂ admin/``is_sys_admin`` ⊂ super-admin). Unlike the two
lower tiers it is **not** a DB column — it is derived from the
deployer-set ``SUPER_ADMIN_EMAILS`` config (email membership,
case-insensitive), so it cannot drift from config or be flipped from
inside the app. This module is the single resolver both the identity
seam (``app/web/deps.py``) and the user-management guards
(``app/services/users.py``) consult.

Kept dependency-free (imports only ``app.config``) so callers on
either side of the route/service split can use it without import
cycles.
"""
from __future__ import annotations

from app.config import Settings, settings as default_settings


def effective_super_admin_emails(settings: Settings | None = None) -> list[str]:
    """The super-admin email set the resolver consults.

    The configured ``super_admin_emails`` plus — **only** in a
    fake-auth sandbox — the fake identity's email. That fold-in lets
    the localhost operator (``fake_auth_email``, default
    ``operator@example.edu``) hold super-admin for testing without any
    env coordination, while keeping the "derived from config, never
    stored" invariant: the fake email is not a real
    ``SUPER_ADMIN_EMAILS`` entry, just part of the effective set. Inert
    in any deployed environment, where ``allow_fake_auth`` must be
    false.
    """
    s = settings or default_settings
    emails = list(s.super_admin_emails)
    if s.allow_fake_auth and s.fake_auth_super_admin:
        emails.append(s.fake_auth_email)
    return emails


def is_super_admin(email: str | None, settings: Settings | None = None) -> bool:
    """True when ``email`` is a super-admin.

    Case-insensitive membership in the effective super-admin set.
    Empty / missing email is never a super-admin.
    """
    if not email:
        return False
    target = email.casefold()
    return any(
        item.casefold() == target
        for item in effective_super_admin_emails(settings)
    )
