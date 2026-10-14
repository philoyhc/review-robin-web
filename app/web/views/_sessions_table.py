"""The session tables' shared shape: the Sessions lobby, its Archive
child and Sys Admin → Sessions Diagnostics all sort the same columns the
same way (the ``rrw-sortable`` primitive, cookie-seeded on the server),
and Diagnostics filters on name, code and owner.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from app.db.models import ReviewSession, User
from app.services import sessions

__all__ = [
    "ARCHIVED_SORT_KEYS",
    "DIAGNOSTICS_SORT_KEYS",
    "LOBBY_SORT_KEYS",
    "diagnostics_filter_options",
    "diagnostics_filter_text",
    "session_sort_value",
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
    if key == "name":
        return review_session.name
    if key == "code":
        return review_session.code
    if key == "created_by":
        return review_session.created_by_user.display_label
    if key == "created":
        return review_session.created_at
    if key == "deadline":
        return review_session.deadline
    if key == "archived":
        return review_session.updated_at
    if key == "timezone":
        return sessions.resolve_session_timezone(review_session)
    if key == "status":
        return review_session.status
    return None


def diagnostics_filter_text(review_session: ReviewSession, owners: Iterable[User]) -> str:
    """What the Diagnostics filter matches a row against, lower-cased:
    the name, the code, and each owner's name and email, one per line so
    a term can't match across two of them."""
    parts = [review_session.name or "", review_session.code or ""]
    for owner in owners:
        parts.append(owner.display_name or "")
        parts.append(owner.email)
    return "\n".join(part for part in parts if part).casefold()


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
