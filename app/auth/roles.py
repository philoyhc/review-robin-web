"""Super-admin, as RRW reads it (Segment 18S Item 1; segment 21C).

Super-admin is the top tier of the three-tier role model
(operator ⊂ admin/``is_sys_admin`` ⊂ super-admin). Unlike the two
lower tiers it is **not** a DB column: it is Cordware's platform role,
derived from the deployer-set ``SUPER_ADMIN_EMAILS`` plus the fake
account under local fake auth (``cordware.identity``), so it cannot
drift from config or be flipped from inside the app. This module is the
one place RRW reads it, for both the identity seam
(``app/web/deps.py``) and the user-management guards
(``app/services/users.py``).

``super_admin_configured()`` is the no-super-tier fallback's test: with
none configured, any admin manages admins (18S Item 2).
"""
from __future__ import annotations

from cordware.identity import (
    is_super_admin_email,
    super_admin_configured,
    super_admin_emails,
)


def is_super_admin(email: str | None) -> bool:
    """True when ``email`` is a super-admin. Case-insensitive; an empty
    or missing email never is."""
    return is_super_admin_email(email)


__all__ = ["is_super_admin", "super_admin_configured", "super_admin_emails"]
