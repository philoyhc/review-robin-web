"""The people search (segment AD2A; ruling 75): every place that adds a
person searches by name or email, people already on record first, then
the institution's directory through Graph (`cordware/graph.py`,
`search_users`), as Review Robin's pickers do. A local run's directory is
Cordware's fake one, with the sample panels' members added
(`for_request`), so a local check has some fifty accounts to find.

A failed directory search is reported, never read as "nobody there": the
result then holds only people on record and names the failure's kind.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from functools import cache

from fastapi.requests import HTTPConnection
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from applydesk.models import Person
from cordware.graph import (
    FAKE_USERS,
    Directory,
    DirectoryUser,
    FakeDirectory,
    GraphError,
    directory_for,
)

#: At most this many of each kind of match.
LIMIT = 20
#: Shorter queries search nothing: two letters already match too many.
MIN_QUERY = 2


@cache
def _local_users() -> tuple[DirectoryUser, ...]:
    """Cordware's fake accounts, then every sample panel's members not
    already among them (author, 2026-11-27: the RA exercise's panels make
    a longer list of institutional accounts to check with on localhost).
    Each member's object ID is derived from the address, so it is the same
    on every run."""
    from applydesk import sample_data

    taken = {(u.mail or u.user_principal_name).lower() for u in FAKE_USERS}
    added: list[DirectoryUser] = []
    for panel in sample_data.PANELS:
        for member in panel.members:
            address = member.email.lower()
            if address in taken:
                continue
            taken.add(address)
            object_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"mailto:{address}"))
            added.append(DirectoryUser(object_id, member.name, address, address))
    return (*FAKE_USERS, *added)


def for_request(request: HTTPConnection) -> Directory:
    """The directory as the request's user sees it (`directory_for`); a
    local run's fake directory also finds the sample panels' members."""
    found = directory_for(request)
    return FakeDirectory(_local_users()) if type(found) is FakeDirectory else found


@dataclass(frozen=True)
class SearchResult:
    on_record: tuple[Person, ...]
    in_directory: tuple[DirectoryUser, ...]
    directory_failed: str | None = None


def escape_like(text: str) -> str:
    """`text` safe inside a LIKE pattern escaped by a backslash."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def search(
    session: Session,
    query: str,
    directory: Directory | None,
    *,
    allowlist_only: bool = False,
    exclude: frozenset[int] = frozenset(),
) -> SearchResult:
    """People matching `query` by name or address: those on record (only
    the allowlist's, with `allowlist_only`; never the rows in `exclude`,
    left out before the limit), then the directory's not already on
    record. No directory (None) searches records alone."""
    text = query.strip()
    if len(text) < MIN_QUERY:
        return SearchResult((), ())
    like = f"%{escape_like(text.casefold())}%"
    statement = select(Person).where(
        or_(
            Person.email_key.like(like, escape="\\"),
            Person.display_name_key.like(like, escape="\\"),
        )
    )
    if allowlist_only:
        statement = statement.where(Person.may_operate.is_(True))
    if exclude:
        statement = statement.where(Person.id.not_in(exclude))
    on_record = tuple(
        session.scalars(
            statement.order_by(Person.display_name.is_(None), Person.display_name, Person.id).limit(
                LIMIT
            )
        )
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
