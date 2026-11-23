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

from sqlalchemy import and_, case, exists, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from applydesk import directory, operators, people
from applydesk.directory import escape_like
from applydesk.models import AuditEvent, ExerciseOperator, Person
from cordware.graph import Directory, GraphError
from cordware.identity import Identity

#: Workspace users' chips, `(key, label, on by default)` in toolbar order
#: (segment AD2W, as Review Robin's `ACCOUNT_CATEGORIES`).
CATEGORIES: tuple[tuple[str, str, bool], ...] = (
    ("operators", "Operators", True),
    ("admins", "Admins", True),
    ("no_role", "No role", False),
    ("unused", "Unused", False),
)
DEFAULT_SHOW = frozenset(key for key, _, on in CATEGORIES if on)

#: The Exercise role dropdown, `(value, label)`.
ROLES: tuple[tuple[str, str], ...] = (
    ("any", "Any"),
    ("owner", "Owner of an exercise"),
    ("operator", "Operator of an exercise"),
    ("none", "No exercise"),
)


def _current_grant(*, owner: bool = False) -> ColumnElement[bool]:
    held: list[ColumnElement[bool]] = [
        ExerciseOperator.person_id == Person.id,
        ExerciseOperator.removed_at.is_(None),
    ]
    if owner:
        held.append(ExerciseOperator.is_owner.is_(True))
    return exists().where(*held)


def _has_history() -> ColumnElement[bool]:
    """Ever admitted, ever granted an exercise, or ever acted: such a
    person is *No role* rather than *Unused* when they hold neither."""
    return or_(
        Person.admitted_at.is_not(None),
        exists().where(ExerciseOperator.person_id == Person.id),
        exists().where(AuditEvent.actor_id == Person.id),
    )


def _category(admin_id: int | None) -> ColumnElement[str]:
    """Each person under exactly one chip, as Review Robin's: the admin
    first (the super-admin's own row), then operators, then history."""
    return case(
        (
            or_(
                Person.id == (admin_id if admin_id is not None else -1),
                and_(
                    Person.is_admin.is_(True),
                    Person.may_operate.is_(True),
                    Person.revoked_at.is_(None),
                ),
            ),
            "admins",
        ),
        (and_(Person.may_operate.is_(True), Person.revoked_at.is_(None)), "operators"),
        (_has_history(), "no_role"),
        else_="unused",
    )


def _role_filter(role: str) -> ColumnElement[bool] | None:
    if role == "owner":
        return _current_grant(owner=True)
    if role == "operator":
        return _current_grant()
    if role == "none":
        return ~_current_grant()
    return None


def _matching(query: str) -> ColumnElement[bool] | None:
    text = query.strip().casefold()
    if not text:
        return None
    like = f"%{escape_like(text)}%"
    return or_(
        Person.email_key.like(like, escape="\\"),
        Person.display_name_key.like(like, escape="\\"),
    )


@dataclass(frozen=True)
class Accounts:
    """One view of Workspace users: the rows shown, each chip's count
    under the role and search, whether the super-admin's own row leads
    (only when they have no person row), and the filters as read."""

    people: list[Person]
    counts: dict[str, int]
    show: frozenset[str]
    role: str
    query: str
    me_row: bool


def accounts(
    session: Session, me: Me, *, show: frozenset[str], role: str = "any", query: str = ""
) -> Accounts:
    """Workspace users under the `show` chips, the exercise `role` and the
    search `query` (segment AD2W). The chips' counts take the role and the
    search but not the chips, as Review Robin's do. Unknown chips and
    roles are ignored."""
    role = role if role in dict(ROLES) else "any"
    show = show & {key for key, _, _ in CATEGORIES}
    category = _category(me.person_id)
    filters = [f for f in (_role_filter(role), _matching(query)) if f is not None]
    counted = dict(
        session.execute(
            select(category, func.count()).select_from(Person).where(*filters).group_by(category)
        ).all()
    )
    counts = {key: int(counted.get(key, 0)) for key, _, _ in CATEGORIES}
    # The super-admin's own row, when Apply Desk has no person row for
    # them: an admin with no exercise, matched on the identity's fields.
    me_row = (
        me.is_super_admin and me.person_id is None and role in ("any", "none") and me.matches(query)
    )
    if me_row:
        counts["admins"] += 1
    people = list(
        session.scalars(
            select(Person)
            .where(category.in_(show), *filters)
            .order_by(
                Person.display_name.is_(None), Person.display_name, Person.email_key, Person.id
            )
        )
    )
    return Accounts(people, counts, show, role, query, me_row and "admins" in show)


@dataclass(frozen=True)
class Me:
    """The signed-in super-admin, shown on the list as *(self)* as Review
    Robin's Accounts Management shows them (the author's ask, 2026-11-21):
    they reach every page by their identity, not by being on the list.
    `person_id` is their row, if they have one."""

    email: str
    name: str
    person_id: int | None
    is_super_admin: bool = False  # an Admin's own row is theirs, not the super-admin's

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
    return Me(
        identity.mail or identity.email or "", identity.name or "", row, identity.is_super_admin
    )


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
        not_signed_in=session.scalar(count.where(*listed, Person.first_signed_in_at.is_(None)))
        or 0,
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
    session: Session,
    query: str,
    make_directory: Callable[[], Directory],
    exclude: frozenset[int] = frozenset(),
) -> directory.SearchResult:
    """The people search (`directory.search`) for the page: a directory that
    cannot even be reached (no token) is reported as a failure, the people
    on record still shown. `exclude` leaves those rows out before the
    search's limit."""
    try:
        reached = make_directory()
    except GraphError as error:
        found = directory.search(session, query, None, exclude=exclude)
        return directory.SearchResult(found.on_record, (), directory_failed=error.kind)
    return directory.search(session, query, reached, exclude=exclude)


def suggest(
    session: Session, query: str, make_directory: Callable[[], Directory]
) -> dict[str, object]:
    """The *Add an operator* box's offers for `query`: people on the list
    are left out in the search, before its limit, and so are their entries
    in the directory (Codex on #4122)."""
    listed = listed_ids(session)
    found = search(session, query, make_directory, exclude=frozenset(p.id for p in listed))
    bound = {p.object_id for p in listed if p.object_id}
    kept = tuple(u for u in found.in_directory if u.id not in bound)
    return suggestions(directory.SearchResult(found.on_record, kept, found.directory_failed), set())


def suggestions(found: directory.SearchResult, listed: set[int]) -> dict[str, object]:
    """The *Add an operator* box's offers (segment AD2W, after Review
    Robin's invite picker): people on record not already on the list, then
    the directory's, each with what a pick posts and the label it shows
    ("Name <address>"). `available` is false when the directory did not
    answer, `reason` then saying why; people on record still come."""

    def label(name: str | None, address: str | None) -> str:
        return f"{name} <{address}>" if name and address else (address or name or "")

    offers: list[dict[str, object]] = []
    for p in found.on_record:
        if p.id not in listed:
            offers.append(
                {"label": label(p.display_name, p.email), "person_id": p.id, "where": "On record"}
            )
    for u in found.in_directory:
        address = u.mail or u.user_principal_name
        offers.append(
            {
                "label": label(u.display_name, address),
                "object_id": u.id,
                "address": address,
                "where": "Directory",
            }
        )
    # Each label names one pick: the box finds a pick by its label, so two
    # people with one name and address would otherwise share a pick, and
    # choosing the first would admit the second (Codex on #4122). Repeats
    # are numbered in the order offered.
    seen: dict[str, int] = {}
    for offer in offers:
        text = str(offer["label"])
        seen[text] = seen.get(text, 0) + 1
        if seen[text] > 1:
            offer["label"] = f"{text} ({str(offer['where']).lower()} {seen[text]})"
    answer: dict[str, object] = {"available": found.directory_failed is None, "people": offers}
    if found.directory_failed:
        answer["reason"] = found.directory_failed
    return answer


def actor_for(session: Session, identity: Identity) -> operators.Actor:
    """The super-admin or an Admin acting, with their person row where they
    can be bound (their changes then name them). Each change checks again
    what the actor may do (`operators.keeps_the_list`, `makes_admins`)."""
    return operators.Actor(
        people.resolve(session, identity), is_super_admin=identity.is_super_admin
    )


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


@dataclass(frozen=True)
class Bulk:
    """What a bulk *Admit* or *Revoke* did: how many changed, how many
    were skipped (already so, gone, or the super-admin's own row)."""

    changed: int
    skipped: int


#: The bulk bar's actions (segments AD2W, AD2M), each through `operators`.
BULK_ACTIONS: dict[str, Callable[[Session, operators.Actor, Person], None]] = {
    "admit": operators.admit,
    "revoke": operators.revoke,
    "promote": operators.promote,
    "demote": operators.demote,
}


def bulk(
    session: Session, actor: operators.Actor, action: str, person_ids: list[int], me: Me
) -> Bulk:
    """*Admit*, *Revoke*, *Promote* or *Demote* every ticked row (segments
    AD2W, AD2M), each through `operators` and audited there, in the caller's one
    transaction. A refusal skips that person, not the batch: a refusal
    changes nothing, so the transaction stays good. The super-admin's own
    row is always skipped (no action on your own row)."""
    change = BULK_ACTIONS[action]
    changed = skipped = 0
    # Each once, in ID order: two overlapping posts lock rows in one order.
    for person_id in sorted(set(person_ids)):
        person = session.get(Person, person_id)
        if person is None or person_id == me.person_id:
            skipped += 1
            continue
        try:
            change(session, actor, person)
        except operators.Refused:
            skipped += 1
            continue
        changed += 1
    return Bulk(changed, skipped)
