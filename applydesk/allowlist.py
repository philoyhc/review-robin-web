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

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from applydesk import operators, people
from applydesk.models import Person
from cordware.graph import Directory
from cordware.identity import Identity


@dataclass(frozen=True)
class Entry:
    """One row of the list."""

    person: Person
    admitted_at: datetime | None
    admitted_by: Person | None


def listing(session: Session) -> list[Entry]:
    """Everyone on the list, by name then address."""
    admitter = aliased(Person)
    rows = session.execute(
        select(Person, admitter)
        .outerjoin(admitter, admitter.id == Person.admitted_by_id)
        .where(Person.may_operate.is_(True), Person.revoked_at.is_(None))
        .order_by(Person.display_name, Person.email_key, Person.id)
    ).all()
    return [Entry(person, person.admitted_at, by) for person, by in rows]


def actor_for(session: Session, identity: Identity) -> operators.Actor:
    """The super-admin acting, with their person row where they can be
    bound (their admissions then name them)."""
    return operators.Actor(people.resolve(session, identity), is_super_admin=True)


def admit_on_record(session: Session, actor: operators.Actor, person_id: int) -> Person:
    person = session.get(Person, person_id)
    if person is None:
        raise operators.Refused("That person is no longer on record.")
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
        raise operators.Refused("The directory no longer has that account; search again.")
    person = people.from_directory(session, found, tenant_id, actor.person)
    operators.admit(session, actor, person)
    return person


def revoke(session: Session, actor: operators.Actor, person_id: int) -> Person:
    person = session.get(Person, person_id)
    if person is None:
        raise operators.Refused("That person is no longer on record.")
    operators.revoke(session, actor, person)
    return person
