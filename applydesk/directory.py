"""The people search (segment AD2A; ruling 75): every place that adds a
person searches by name or email, people already on record first, then
the institution's directory through Graph (`cordware/graph.py`,
`search_users`), as Review Robin's pickers do. A local run's directory is
Cordware's fake one.

A failed directory search is reported, never read as "nobody there": the
result then holds only people on record and names the failure's kind.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from applydesk.models import Person
from cordware.graph import Directory, DirectoryUser, GraphError

#: At most this many of each kind of match.
LIMIT = 20
#: Shorter queries search nothing: two letters already match too many.
MIN_QUERY = 2


@dataclass(frozen=True)
class SearchResult:
    on_record: tuple[Person, ...]
    in_directory: tuple[DirectoryUser, ...]
    directory_failed: str | None = None


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search(
    session: Session,
    query: str,
    directory: Directory | None,
    *,
    allowlist_only: bool = False,
) -> SearchResult:
    """People matching `query` by name or address: those on record (only
    the allowlist's, with `allowlist_only`), then the directory's not
    already on record. No directory (None) searches records alone."""
    text = query.strip()
    if len(text) < MIN_QUERY:
        return SearchResult((), ())
    like = f"%{_escape(text.casefold())}%"
    statement = select(Person).where(
        or_(
            Person.email_key.like(like, escape="\\"),
            func.lower(Person.display_name).like(like, escape="\\"),
        )
    )
    if allowlist_only:
        statement = statement.where(Person.may_operate.is_(True))
    on_record = tuple(
        session.scalars(statement.order_by(Person.display_name, Person.id).limit(LIMIT))
    )
    if allowlist_only or directory is None:
        return SearchResult(on_record, ())
    try:
        found = directory.search_users(text)
    except GraphError as error:
        return SearchResult(on_record, (), directory_failed=error.kind)
    # A bound person is the same account only by object ID; their email is
    # a snapshot, and a reassigned address is another account (Codex on
    # #4110). Only a pending person is matched by address.
    known = {p.object_id for p in on_record if p.object_id}
    known_keys = {p.email_key for p in on_record if p.email_key and not p.object_id}
    fresh = tuple(
        user
        for user in found
        if user.id not in known
        and (user.mail or user.user_principal_name).casefold() not in known_keys
    )[:LIMIT]
    return SearchResult(on_record, fresh)
