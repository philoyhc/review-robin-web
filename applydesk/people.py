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
from typing import Any, cast

from sqlalchemy import CursorResult, select, update
from sqlalchemy.exc import IntegrityError
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


def _bind(
    session: Session, person: Person, account: Account, how: str, actor: Person | None
) -> Person | None:
    """Bind the pending `person` to `account`, only if it is still unbound:
    a conditional update, so of two requests binding one pending row at
    once only the first wins (Codex on #4110). None if another request
    bound it first; the caller looks again."""
    email = account.email or person.email
    savepoint = session.begin_nested()
    try:
        claimed = cast(
            "CursorResult[Any]",
            session.execute(
                update(Person)
                .where(Person.id == person.id, Person.object_id.is_(None))
                .values(
                    tenant_id=account.tenant_id,
                    object_id=account.object_id,
                    email=email,
                    email_key=email_key(email),
                    upn=account.upn or person.upn,
                    display_name=account.name or person.display_name,
                    bound_at=datetime.now(UTC),
                )
                .execution_options(synchronize_session=False)
            ),
        )
        savepoint.commit()
    except IntegrityError:  # another request stored this account meanwhile
        savepoint.rollback()
        session.expire(person)
        return None
    if claimed.rowcount != 1:
        session.expire(person)
        return None
    session.refresh(person)
    audit.write_event(
        session,
        event_type="person.bound",
        actor=person if how == "sign_in" else actor,
        payload=audit.snapshot(_snapshot(person)),
        refs={"person_id": person.id},
        context={"how": how},
    )
    return person


def _new_bound(session: Session, account: Account, how: str, actor: Person | None) -> Person | None:
    """A new person bound to `account`. None if another request stored that
    account first (the unique (tenant, object ID) refused this insert): the
    savepoint undoes only the insert, and the caller looks again (Codex on
    #4110)."""
    person = Person(
        tenant_id=account.tenant_id,
        object_id=account.object_id,
        email=account.email,
        email_key=email_key(account.email),
        upn=account.upn,
        display_name=account.name,
        bound_at=datetime.now(UTC),
    )
    try:
        with session.begin_nested():
            session.add(person)
    except IntegrityError:
        return None
    audit.write_event(
        session,
        event_type="person.created",
        actor=person if how == "sign_in" else actor,
        payload=audit.snapshot(_snapshot(person)),
        refs={"person_id": person.id},
        context={"how": how},
    )
    return person


#: Looks a binding makes before giving up: each lost race means another
#: request bound the pending row or stored the account, so the next look
#: finds the bound person, another pending one, or none.
_ATTEMPTS = 3


def _attach(
    session: Session,
    account: Account,
    keys: tuple[str | None, ...],
    how: str,
    actor: Person | None,
) -> Person:
    """The person for `account`: the bound one; else a pending one matching
    `keys`, bound; else a new bound one. A pending row another request
    bound first is passed over and the look repeated."""
    for _ in range(_ATTEMPTS):
        person = _bound_person(session, account.tenant_id, account.object_id)
        if person is not None:
            return person
        found = _pending_person(session, *keys)
        if found is None:
            made = _new_bound(session, account, how=how, actor=actor)
        else:
            made = _bind(session, found, account, how=how, actor=actor)
        if made is not None:
            return made
    raise RuntimeError("could not bind the account: another request kept taking it")


def resolve(session: Session, identity: Identity) -> Person | None:
    """The signed-in person, bound to their account: found by (tenant,
    object ID); else a pending person matching the UPN, then the mail, is
    bound; else a new bound person is made. None for an identity with no
    tenant or object ID, which cannot be bound. Flushes; the caller commits."""
    tenant_id = (identity.tenant_id or "").strip()
    object_id = (identity.principal_id or "").strip()
    if not tenant_id or not object_id:
        return None
    mail = identity.mail or identity.email
    account = Account(tenant_id, object_id, mail, identity.upn, identity.name)
    return _attach(session, account, (email_key(identity.upn), email_key(mail)), "sign_in", None)


def from_directory(
    session: Session, user: DirectoryUser, tenant_id: str, actor: Person | None
) -> Person:
    """The person a directory search found (ruling 75): stored bound, the
    tenant being the searcher's own. An existing bound row is reused; a
    pending one with the same address is bound. `actor` is who searched
    (None for the super-admin with no row), and the audit names them: the
    person found did nothing. Flushes."""
    mail = user.mail or user.user_principal_name
    account = Account(tenant_id, user.id, mail, user.user_principal_name, user.display_name)
    keys = (email_key(user.user_principal_name), email_key(mail))
    return _attach(session, account, keys, "directory", actor)


def pending(session: Session, address: str, actor: Person | None) -> Person:
    """A person known only by `address`, for an address the directory did
    not find: an existing *pending* row with that address is reused. A
    bound person's address is only a snapshot, never matched on (Codex on
    #4110), so a bound row with it is left alone and a pending one made.
    One pending person per address is the database's rule too: if another
    request made it meanwhile, that one is returned. Flushes."""
    key = email_key(address)
    if key is None:
        raise ValueError("an address is needed")
    for _ in range(_ATTEMPTS):
        existing = _pending_person(session, key)
        if existing is not None:
            return existing
        person = Person(email=address.strip(), email_key=key)
        try:
            with session.begin_nested():
                session.add(person)
        except IntegrityError:
            continue  # another request made it meanwhile: look again
        break
    else:
        raise RuntimeError("could not store the address: another request kept taking it")
    audit.write_event(
        session,
        event_type="person.created",
        actor=actor,
        payload=audit.snapshot(_snapshot(person)),
        refs={"person_id": person.id},
        context={"how": "address"},
    )
    return person
