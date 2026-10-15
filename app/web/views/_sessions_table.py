"""The session tables' shared shape: the Sessions lobby, its Archive
child and Sys Admin → Sessions Diagnostics all sort the same columns the
same way (the ``rrw-sortable`` primitive, cookie-seeded on the server),
and Diagnostics filters on name, code and owner.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import datetime

from app.db.models import ReviewSession, User
from app.services import date_formatting, sessions
from app.services.session_lifecycle import SessionStatus

__all__ = [
    "ARCHIVED_SORT_KEYS",
    "DIAGNOSTICS_SORT_KEYS",
    "LOBBY_SORT_KEYS",
    "diagnostics_filter_options",
    "diagnostics_filter_text",
    "instant_sort_value",
    "session_sort_value",
    "status_sort_cell",
    "status_sort_value",
    "text_sort_value",
]

LOBBY_SORT_KEYS = frozenset(
    {"name", "code", "created_by", "created", "deadline", "timezone", "status"}
)
# The archived table shows "Archived" where the lobby shows "Deadline" —
# ``updated_at``, since an archived session is inert and its last
# mutation is the archive itself.
ARCHIVED_SORT_KEYS = frozenset(
    {"name", "code", "created_by", "created", "archived", "timezone", "status"}
)
# Diagnostics sorts the lobby's columns but Status (author, 2026-10-14).
DIAGNOSTICS_SORT_KEYS = LOBBY_SORT_KEYS - {"status"}


def session_sort_value(review_session: ReviewSession, key: str):
    """The value a session table sorts ``key`` by, server side."""
    # Text sorts as a header click does (author, 2026-10-15).
    if key == "name":
        return text_sort_value(review_session.name)
    if key == "code":
        return text_sort_value(review_session.code)
    if key == "created_by":
        return text_sort_value(review_session.created_by_user.display_label)
    if key == "created":
        return review_session.created_at
    if key == "deadline":
        return review_session.deadline
    if key == "archived":
        return review_session.updated_at
    if key == "timezone":
        return sessions.resolve_session_timezone(review_session)
    if key == "status":
        return status_sort_value(review_session.status)
    return None


_DIGIT_RUNS = re.compile(r"(\d+)")


def text_sort_value(value: str | None) -> tuple | None:
    """A text cell's server sort key, ordered as the browser orders the
    cell on a header click (`localeCompare` with `numeric: true`, over
    the trimmed text): case aside, so "alpha" precedes "Beta", and runs
    of digits as numbers, so "Session 2" precedes "Session 10". Python's
    `<` alone did neither. The key alternates text and number (text at
    even places, int at odd), so any two keys compare like with like.
    A text part that a number follows ends in "0", standing in for the
    digit (text parts hold none of their own), so a space or a mark
    below "0" (`-`, `.`, `#`, `/`) there still sorts before it, as in the
    browser: "Session 2" before "Session1", "a-1" before "a1". None for
    an empty value, which sorts last either way. Accents, punctuation
    (how "_", ":" and other symbols rank against digits and letters, and
    two marks against each other) and names differing only in case can
    still order differently in the browser, whose collation is the
    viewer's locale's."""
    if value is None or not value.strip():
        return None
    parts = _DIGIT_RUNS.split(value.strip().casefold())
    last = len(parts) - 1
    return tuple(
        int(part) if index % 2 else part + "0" if index < last else part
        for index, part in enumerate(parts)
    )


# Lifecycle order (author, 2026-10-15), as `SessionStatus` declares it:
# draft, validated, ready, expired, archived.
_STATUS_ORDER = {status.value: index for index, status in enumerate(SessionStatus)}


def status_sort_value(status: str) -> int | None:
    """A status's place in the lifecycle, so Status sorts Draft →
    Validated → Activated → Closed rather than by its enum string or its
    label; None (last either way) for a status the enum doesn't know."""
    return _STATUS_ORDER.get(status)


def status_sort_cell(status: str) -> str:
    """The Status cell's client sort key (the `sort_status` filter): the
    same number as text, so a header click orders rows as a reload does,
    or "" (last either way) where `status_sort_value` is None."""
    value = status_sort_value(status)
    return "" if value is None else str(value)


def instant_sort_value(value: datetime | None) -> str:
    """A stored instant's client sort key (the `sort_instant` filter, on
    the session tables' Deadline, Created and Archived cells): UTC as
    ISO 8601, normalised as every other render is, so the browser orders
    it as the route does whatever zone the cell is shown in; "" for
    none, which the sort primitive puts last either way. Always to the
    microsecond: a variable width would collate "12:00:00.5" before
    "12:00:00" in the browser, and the cell's own minutes would tie
    rows the route tells apart."""
    return date_formatting.iso_in_zone(value, "UTC", timespec="microseconds")


def diagnostics_filter_text(review_session: ReviewSession, owners: Iterable[User]) -> str:
    """What the Diagnostics filter matches a row against, lower-cased as
    the browser lower-cases the term (`toLowerCase`, so not `casefold`):
    the name, the code, and each owner's name and email, one per line so
    a term can't match across two of them."""
    parts = [review_session.name or "", review_session.code or ""]
    for owner in owners:
        parts.append(owner.display_name or "")
        parts.append(owner.email)
    return "\n".join(part for part in parts if part).lower()


def owned_session_ids(
    owners_by_session: Mapping[int, list[User]], user: User
) -> set[int]:
    """The sessions ``user`` already owns, whose Diagnostics row shows a
    grayed-out **Owned** in place of Manage (author, 2026-10-15)."""
    return {
        session_id
        for session_id, owners in owners_by_session.items()
        if any(owner.id == user.id for owner in owners)
    }


def diagnostics_filter_options(
    rows: Iterable[ReviewSession], owners_by_session: Mapping[int, list[User]]
) -> list[str]:
    """The Diagnostics filter's typeahead: every session name and code,
    then every owner's label, each once."""
    seen: set[str] = set()
    handles: list[str] = []
    owners: list[str] = []
    for row in rows:
        for value, bucket in (
            (row.name, handles),
            (row.code, handles),
            *((owner.display_label, owners) for owner in owners_by_session.get(row.id, [])),
        ):
            value = (value or "").strip()
            if value and value.casefold() not in seen:
                seen.add(value.casefold())
                bucket.append(value)
    return sorted(handles, key=str.casefold) + sorted(owners, key=str.casefold)
