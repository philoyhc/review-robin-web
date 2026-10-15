"""Small participant-facing adapters: which top bar a shared page
shows, the masked invited address, and the one-line notices ``/me``
shows after a redirect (participant audit M8, M9, M11; author's rulings
2026-10-15)."""

from __future__ import annotations

from typing import Any

# The notices ``/me`` shows after sending someone there, keyed by a
# fixed ``?notice=`` value so the query string can never carry text of
# its own onto the page (M11). An unknown key shows nothing.
ME_NOTICES: dict[str, str] = {
    "summary": "Your summary is available once every review is submitted.",
    "organizers": "That page is for the people who run reviews.",
}


def uses_participant_chrome(user: Any) -> bool:
    """Whether About, Guide and Sign-in details show the participant top
    bar rather than the operator one (M8): everyone but operators and
    system admins. ``user`` may be ``None`` (no row could be found)."""
    if user is None:
        return True
    return not (
        getattr(user, "is_operator", False) or getattr(user, "is_sys_admin", False)
    )


def masked_email(address: str | None) -> str:
    """The invited address, partly hidden (M9): the first character of
    the local part, then ``•••``, then the domain, so its owner can
    recognize it and whoever holds a forwarded link learns little."""
    address = (address or "").strip()
    local, at, domain = address.partition("@")
    if not at:
        return "•••"
    return f"{local[:1]}•••@{domain}"


def me_notice(key: str | None) -> str | None:
    return ME_NOTICES.get(key or "")
