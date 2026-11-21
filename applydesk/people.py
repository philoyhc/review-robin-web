"""People and their binding (segment AD2A; ruling 73), as Residential's
(`residentialapps/docs/residentialapps_email_identity_matching.md`).

A person is bound by (tenant, object ID). Someone known only by an
address waits as a *pending* person, found by `email_key` (the casefolded
address), and is bound when they first sign in, or at once when they come
from a directory search, which gives the object ID. After binding, email,
UPN and name are snapshots only: nothing matches on them again.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from applydesk import audit
from applydesk.models import Person
from cordware.graph import DirectoryUser
from cordware.identity import Identity


@dataclass(frozen=True)
class Account:
    """An account as a sign-in or the directory gives it."""

    tenant_id: str
    object_id: str
    email: str | None
    upn: str | None
    name: str | None


def email_key(address: str | None) -> str | None:
    """The match key for an address: trimmed and casefolded; None if empty."""
    if address is None:
        return None
    key = address.strip().casefold()
    return key or None


def _snapshot(person: Person) -> dict[str, object]:
    return {"email": person.email, "display_name": person.display_name, "pending": not person.bound}


def _bound_person(session: Session, tenant_id: str, object_id: str) -> Person | None:
    return session.scalar(
        select(Person).where(Person.tenant_id == tenant_id, Person.object_id == object_id)
    )


def _pending_person(session: Session, *keys: str | None) -> Person | None:
    """A pending person whose address matches any of `keys`, tried in order
    (Residential's rule: the UPN and the mail separately)."""
    for key in keys:
        if key is None:
            continue
        person = session.scalar(
            select(Person)
            .where(Person.email_key == key, Person.object_id.is_(None))
            .order_by(Person.id)
        )
        if person is not None:
            return person
    return None


def _bind(session: Session, person: Person, account: Account, how: str) -> Person:
    person.tenant_id = account.tenant_id
    person.object_id = account.object_id
    person.email = account.email or person.email
    person.email_key = email_key(person.email)
    person.upn = account.upn or person.upn
    person.display_name = account.name or person.display_name
    person.bound_at = datetime.now(UTC)
    session.flush()
    audit.write_event(
        session,
        event_type="person.bound",
        actor=person,
        payload=audit.snapshot(_snapshot(person)),
        context={"how": how},
    )
    return person


def _new_bound(session: Session, account: Account, how: str) -> Person:
    person = Person(
        tenant_id=account.tenant_id,
        object_id=account.object_id,
        email=account.email,
        email_key=email_key(account.email),
        upn=account.upn,
        display_name=account.name,
        bound_at=datetime.now(UTC),
    )
    session.add(person)
    session.flush()
    audit.write_event(
        session,
        event_type="person.created",
        actor=person,
        payload=audit.snapshot(_snapshot(person)),
        context={"how": how},
    )
    return person


def resolve(session: Session, identity: Identity) -> Person | None:
    """The signed-in person, bound to their account: found by (tenant,
    object ID); else a pending person matching the UPN, then the mail, is
    bound; else a new bound person is made. None for an identity with no
    tenant or object ID, which cannot be bound. Flushes; the caller commits."""
    tenant_id = (identity.tenant_id or "").strip()
    object_id = (identity.principal_id or "").strip()
    if not tenant_id or not object_id:
        return None
    person = _bound_person(session, tenant_id, object_id)
    if person is not None:
        return person
    mail = identity.mail or identity.email
    pending = _pending_person(session, email_key(identity.upn), email_key(mail))
    account = Account(tenant_id, object_id, mail, identity.upn, identity.name)
    if pending is not None:
        return _bind(session, pending, account, how="sign_in")
    return _new_bound(session, account, how="sign_in")


def from_directory(session: Session, user: DirectoryUser, tenant_id: str) -> Person:
    """The person a directory search found (ruling 75): stored bound, the
    tenant being the searcher's own. An existing bound row is reused; a
    pending one with the same address is bound. Flushes."""
    person = _bound_person(session, tenant_id, user.id)
    if person is not None:
        return person
    mail = user.mail or user.user_principal_name
    pending = _pending_person(session, email_key(user.user_principal_name), email_key(mail))
    account = Account(tenant_id, user.id, mail, user.user_principal_name, user.display_name)
    if pending is not None:
        return _bind(session, pending, account, how="directory")
    return _new_bound(session, account, how="directory")


def pending(session: Session, address: str, actor: Person | None) -> Person:
    """A person known only by `address`, for an address the directory did
    not find: an existing row with that address is reused. Flushes."""
    key = email_key(address)
    if key is None:
        raise ValueError("an address is needed")
    existing = session.scalar(select(Person).where(Person.email_key == key).order_by(Person.id))
    if existing is not None:
        return existing
    person = Person(email=address.strip(), email_key=key)
    session.add(person)
    session.flush()
    audit.write_event(
        session,
        event_type="person.created",
        actor=actor,
        payload=audit.snapshot(_snapshot(person)),
        context={"how": "address"},
    )
    return person
