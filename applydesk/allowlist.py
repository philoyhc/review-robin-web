"""The operator list's page, wired (segment AD2A, rung 6; ruling 75): who is
on the list, and admitting or revoking someone, for `routes_admin.py`.

Admitting goes through the people search (`directory.py`): someone already
on record by their row, someone found in the directory by their object ID.
A directory pick is looked up again at admission (`find_users` on the
address the page showed, matched on the object ID), so nothing about the
person is taken from the form. Every change is `operators.admit` or
`operators.revoke`, audited there. A refusal raises `operators.Refused`;
a directory that does not answer raises `cordware.graph.GraphError`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from applydesk import directory, operators, people
from applydesk.directory import escape_like
from applydesk.models import Person
from cordware.graph import Directory, GraphError
from cordware.identity import Identity


@dataclass(frozen=True)
class Entry:
    """One row of the list."""

    person: Person
    admitted_at: datetime | None
    admitted_by: Person | None


def listing(session: Session, query: str = "") -> list[Entry]:
    """Everyone on the list, by name then address (no name last, on SQLite
    and Postgres alike); with `query`, those whose name or address holds
    it."""
    admitter = aliased(Person)
    statement = (
        select(Person, admitter)
        .outerjoin(admitter, admitter.id == Person.admitted_by_id)
        .where(Person.may_operate.is_(True), Person.revoked_at.is_(None))
    )
    text = query.strip().casefold()
    if text:
        like = f"%{escape_like(text)}%"
        statement = statement.where(
            or_(
                Person.email_key.like(like, escape="\\"),
                func.lower(Person.display_name).like(like, escape="\\"),
            )
        )
    rows = session.execute(
        statement.order_by(
            Person.display_name.is_(None), Person.display_name, Person.email_key, Person.id
        )
    ).all()
    return [Entry(person, person.admitted_at, by) for person, by in rows]


@dataclass(frozen=True)
class Me:
    """The signed-in super-admin, shown on the list as *(self)* as Review
    Robin's Accounts Management shows them (the author's ask, 2026-11-21):
    they reach every page by their identity, not by being on the list.
    `person_id` is their row, if they have one."""

    email: str
    name: str
    person_id: int | None

    def matches(self, query: str) -> bool:
        text = query.strip().casefold()
        return not text or text in self.email.casefold() or text in self.name.casefold()


def me(session: Session, identity: Identity) -> Me:
    """The super-admin's *(self)* row, read only: nothing is bound here."""
    tenant_id = (identity.tenant_id or "").strip()
    object_id = (identity.principal_id or "").strip()
    row = None
    if tenant_id and object_id:
        row = session.scalar(
            select(Person.id).where(Person.tenant_id == tenant_id, Person.object_id == object_id)
        )
    return Me(identity.mail or identity.email or "", identity.name or "", row)


@dataclass(frozen=True)
class Overview:
    """The Accounts Overview card's counts (after Review Robin's)."""

    listed: int
    not_signed_in: int
    revoked: int


def overview(session: Session) -> Overview:
    listed = (Person.may_operate.is_(True), Person.revoked_at.is_(None))
    count = select(func.count()).select_from(Person)
    return Overview(
        listed=session.scalar(count.where(*listed)) or 0,
        not_signed_in=session.scalar(count.where(*listed, Person.object_id.is_(None))) or 0,
        revoked=session.scalar(count.where(Person.revoked_at.is_not(None))) or 0,
    )


def listed_ids(session: Session) -> list[Person]:
    """Everyone on the list, unfiltered: which search results are on it."""
    return list(
        session.scalars(
            select(Person).where(Person.may_operate.is_(True), Person.revoked_at.is_(None))
        )
    )


def search(
    session: Session, query: str, make_directory: Callable[[], Directory]
) -> directory.SearchResult:
    """The people search (`directory.search`) for the page: a directory that
    cannot even be reached (no token) is reported as a failure, the people
    on record still shown."""
    try:
        reached = make_directory()
    except GraphError as error:
        found = directory.search(session, query, None)
        return directory.SearchResult(found.on_record, (), directory_failed=error.kind)
    return directory.search(session, query, reached)


def actor_for(session: Session, identity: Identity) -> operators.Actor:
    """The super-admin acting, with their person row where they can be
    bound (their admissions then name them)."""
    return operators.Actor(people.resolve(session, identity), is_super_admin=True)


def admit_on_record(session: Session, actor: operators.Actor, person_id: int) -> Person:
    person = session.get(Person, person_id)
    if person is None:
        raise operators.Refused("That person is no longer on record.", key="gone")
    operators.admit(session, actor, person)
    return person


def admit_from_directory(
    session: Session,
    actor: operators.Actor,
    directory: Directory,
    tenant_id: str,
    object_id: str,
    address: str,
) -> Person:
    """Admit the directory account `object_id`, found again by `address`,
    and stored bound in the searcher's tenant."""
    found = next((u for u in directory.find_users(address) if u.id == object_id), None)
    if found is None:
        raise operators.Refused(
            "The directory no longer has that account; search again.", key="gone"
        )
    person = people.from_directory(session, found, tenant_id, actor.person)
    operators.admit(session, actor, person)
    return person


def revoke(session: Session, actor: operators.Actor, person_id: int) -> Person:
    person = session.get(Person, person_id)
    if person is None:
        raise operators.Refused("That person is no longer on record.", key="gone")
    operators.revoke(session, actor, person)
    return person
