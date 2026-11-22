"""Who may operate, and who operates each exercise (segment AD2A; rulings
73 and 75).

- **The allowlist** is the platform super-admin's: `admit` and `revoke`.
  Only an allowlisted person may make an exercise, be added to one, or
  take its ownership. Revoking ends access at once but keeps the grants,
  so re-admitting restores them.
- **An exercise's operators**: its Owner is one of them. Only the Owner,
  or the super-admin, adds and removes operators and hands ownership to
  another current operator. The Owner is never removed, only replaced by
  a handover. There is always exactly one current Owner.

Each change to an exercise's operators first takes that exercise's row
lock, then checks who may act on fresh rows, then makes the change by
conditional updates that restate the rule; so two changes to one exercise
run one after the other, and the loser is refused. Each change is audited
in the same transaction. A refusal raises
`Refused`, its message the rule, fit to show. Functions flush; the caller
commits.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import CursorResult, Update, or_, select, update
from sqlalchemy.orm import Session

from applydesk import audit
from applydesk.models import Exercise, ExerciseOperator, Person
from cordware.identity import super_admin_configured


class Refused(Exception):
    """A change the rules do not allow; the message says which, and `key`
    names the rule for a page's status line (as `scratch.Refused`'s), so
    rewording a message cannot change what a page shows. The caller rolls
    the session back: a refusal raised part-way leaves nothing it should
    keep."""

    def __init__(self, message: str, *, key: str) -> None:
        super().__init__(message)
        self.key = key


def _changed(session: Session, statement: Update) -> bool:
    """Run a conditional update; whether it changed exactly one row. Its
    WHERE restates the rule, so a concurrent change that broke the rule
    first (Postgres re-reads the row once that change commits) leaves it
    changing nothing (Codex on #4110)."""
    result = cast("CursorResult[Any]", session.execute(statement))
    return result.rowcount == 1


@dataclass(frozen=True)
class Actor:
    """Who is acting: their person (None for a super-admin with no row
    yet) and whether they are the platform super-admin. An Admin is read
    from their row, fresh, where it matters (`_admin_now`)."""

    person: Person | None
    is_super_admin: bool = False


def _now() -> datetime:
    return datetime.now(UTC)


def may_operate(person: Person | None) -> bool:
    """On the allowlist and not revoked."""
    return person is not None and person.may_operate and person.revoked_at is None


def _allowed(session: Session, person: Person | None, *, hold: bool = False) -> bool:
    """`may_operate`, read from the database now rather than from the
    session's copy, so a revoke or admit another request committed counts
    (Codex on #4110). Every allowlist check in this module goes through
    it; `may_operate` alone is for a row just read.

    `hold` reads it under a share lock (`FOR SHARE`) kept to the end of
    the transaction, for a check a change rests on: a revoke committing
    meanwhile then waits for the change, rather than the change landing
    for someone already revoked (bug sweep at the AD2A close)."""
    if person is None:
        return False
    session.refresh(
        person,
        attribute_names=["may_operate", "revoked_at"],
        with_for_update={"read": True} if hold else None,
    )
    return may_operate(person)


def is_admin(person: Person | None) -> bool:
    """An Admin, on the operator list (segment AD2M)."""
    return person is not None and person.is_admin and may_operate(person)


def _admin_now(session: Session, person: Person | None) -> bool:
    """`is_admin`, read from the database now and held to the end of the
    transaction, as `_allowed` is: a demotion committing meanwhile waits."""
    if person is None:
        return False
    session.refresh(
        person,
        attribute_names=["is_admin", "may_operate", "revoked_at"],
        with_for_update={"read": True},
    )
    return is_admin(person)


def keeps_the_list(session: Session, actor: Actor) -> bool:
    """Whether `actor` admits and revokes operators: the super-admin or an
    Admin (`applydesk/spec/permissions.md` §2)."""
    return actor.is_super_admin or _admin_now(session, actor.person)


def makes_admins(session: Session, actor: Actor) -> bool:
    """Whether `actor` promotes and demotes Admins: the super-admin; with
    no super-admin configured, any Admin (Review Robin's fallback)."""
    if actor.is_super_admin:
        return True
    return not super_admin_configured() and _admin_now(session, actor.person)


def _lock(session: Session, exercise: Exercise) -> None:
    """Take the exercise's row lock (`SELECT … FOR UPDATE`) before any
    change to its operators, so each change's check of who may act and
    what holds, and the change itself, run one at a time per exercise
    (Codex on #4110). The reads after it load fresh rows, not the
    session's earlier copies. SQLite has no row locks: two requests that
    both read and then write meet as "database is locked", which the
    routes report as a concurrent change (bug sweep at the AD2A close)."""
    session.execute(select(Exercise.id).where(Exercise.id == exercise.id).with_for_update())


def _grant(session: Session, exercise: Exercise, person: Person) -> ExerciseOperator | None:
    return session.scalar(
        select(ExerciseOperator)
        .where(ExerciseOperator.exercise_id == exercise.id, ExerciseOperator.person_id == person.id)
        .execution_options(populate_existing=True)
    )


def current_operators(session: Session, exercise: Exercise) -> list[tuple[Person, bool]]:
    """Each current operator and whether they are the Owner, the Owner
    first, then by name."""
    rows = session.execute(
        select(Person, ExerciseOperator.is_owner)
        .join(ExerciseOperator, ExerciseOperator.person_id == Person.id)
        .where(ExerciseOperator.exercise_id == exercise.id, ExerciseOperator.removed_at.is_(None))
        .order_by(ExerciseOperator.is_owner.desc(), Person.display_name, Person.id)
    ).all()
    return [(person, is_owner) for person, is_owner in rows]


def owners_of(session: Session, exercise: Exercise) -> list[Person]:
    """The exercise's current Owners, read fresh, by name."""
    return list(
        session.scalars(
            select(Person)
            .join(ExerciseOperator, ExerciseOperator.person_id == Person.id)
            .where(
                ExerciseOperator.exercise_id == exercise.id,
                ExerciseOperator.is_owner.is_(True),
                ExerciseOperator.removed_at.is_(None),
            )
            .order_by(Person.display_name, Person.id)
            .execution_options(populate_existing=True)
        )
    )


def owner_labels(session: Session, public_ids: list[str]) -> dict[str, str]:
    """Each exercise's current Owner, as pages name them, by public ID; an
    exercise with no row or no Owner is left out (the Owner columns on
    Admin's Exercises Diagnostics and the Operator Lobby, 2026-11-22)."""
    if not public_ids:
        return {}
    rows = session.execute(
        select(Exercise.public_id, Person)
        .join(ExerciseOperator, ExerciseOperator.exercise_id == Exercise.id)
        .join(Person, Person.id == ExerciseOperator.person_id)
        .where(
            Exercise.public_id.in_(public_ids),
            ExerciseOperator.is_owner.is_(True),
            ExerciseOperator.removed_at.is_(None),
        )
        .order_by(Person.display_name, Person.id)
    ).all()
    # Several Owners read comma-separated (segment AD2M).
    named: dict[str, list[str]] = {}
    for public_id, person in rows:
        named.setdefault(public_id, []).append(person.label)
    return {public_id: ", ".join(labels) for public_id, labels in named.items()}


def _the_platform(actor: Actor) -> bool:
    """The platform acting with no person (the seed): it reaches every
    exercise. A signed-in super-admin does not: they adopt (segment AD2M)."""
    return actor.is_super_admin and actor.person is None


def _may_act(session: Session, actor: Actor, *, hold: bool = False) -> bool:
    """Whether `actor`'s grants count: anyone on the operator list, and the
    super-admin, who needs no listing (ruling 75)."""
    return actor.person is not None and (
        actor.is_super_admin or _allowed(session, actor.person, hold=hold)
    )


def can_operate(session: Session, exercise: Exercise, actor: Actor) -> bool:
    """Whether `actor` reaches `exercise`: a current grant on it, as an
    operator or an Owner (the super-admin included, segment AD2M)."""
    if _the_platform(actor):
        return True
    if not _may_act(session, actor):
        return False
    assert actor.person is not None
    grant = _grant(session, exercise, actor.person)
    return grant is not None and grant.removed_at is None


def operated_exercises(session: Session, actor: Actor) -> list[Exercise]:
    """The exercises `actor` holds a current grant on."""
    if _the_platform(actor):
        return list(session.scalars(select(Exercise).order_by(Exercise.id)))
    if not _may_act(session, actor):
        return []
    assert actor.person is not None
    return list(
        session.scalars(
            select(Exercise)
            .join(ExerciseOperator, ExerciseOperator.exercise_id == Exercise.id)
            .where(
                ExerciseOperator.person_id == actor.person.id,
                ExerciseOperator.removed_at.is_(None),
            )
            .order_by(Exercise.id)
        )
    )


def is_owner(session: Session, exercise: Exercise, actor: Actor) -> bool:
    """Whether `actor` may change `exercise`'s operators: one of its
    current Owners, allowlisted or the super-admin (read fresh)."""
    return _is_owner(session, exercise, actor)


def _is_owner(session: Session, exercise: Exercise, actor: Actor) -> bool:
    if _the_platform(actor):
        return True
    if actor.person is None:
        return False
    grant = _grant(session, exercise, actor.person)  # fresh
    return (
        grant is not None
        and grant.removed_at is None
        and grant.is_owner
        and _may_act(session, actor, hold=True)
    )


# --------------------------------------------------------------------------- #
# The allowlist: the platform super-admin's
# --------------------------------------------------------------------------- #


def admit(session: Session, actor: Actor, person: Person) -> None:
    """Put `person` on the allowlist (ruling 75)."""
    if not keeps_the_list(session, actor):
        raise Refused(
            "Only an Admin or the platform super-admin keeps the operator list.",
            key="not_super_admin",
        )
    listed = Refused("Already allowed to operate.", key="already_listed")
    if _allowed(session, person):
        raise listed
    # Conditional, so of two admissions at once one changes the row and
    # is audited; the other is refused (bug sweep at the AD2A close).
    if not _changed(
        session,
        update(Person)
        .where(
            Person.id == person.id,
            or_(Person.may_operate.is_(False), Person.revoked_at.is_not(None)),
        )
        .values(
            may_operate=True,
            admitted_by_id=actor.person.id if actor.person is not None else None,
            admitted_at=_now(),
            revoked_at=None,
        )
        .execution_options(synchronize_session=False),
    ):
        raise listed
    session.refresh(person)
    audit.write_event(
        session, event_type="person.admitted", actor=actor.person, refs={"person_id": person.id}
    )


def revoke(session: Session, actor: Actor, person: Person, reason: str | None = None) -> None:
    """Take `person` off the allowlist: their access ends, their grants are
    kept (re-admitting restores them). An Admin is demoted first."""
    if not keeps_the_list(session, actor):
        raise Refused(
            "Only an Admin or the platform super-admin keeps the operator list.",
            key="not_super_admin",
        )
    unlisted = Refused("Not on the operator list.", key="not_listed")
    if not _allowed(session, person):
        raise unlisted
    if person.is_admin:
        raise Refused("An Admin is demoted before being taken off the list.", key="is_admin")
    # Conditional, as `admit`: two revocations at once audit once.
    if not _changed(
        session,
        update(Person)
        .where(
            Person.id == person.id,
            Person.may_operate.is_(True),
            Person.revoked_at.is_(None),
            Person.is_admin.is_(False),
        )
        .values(may_operate=False, revoked_at=_now())
        .execution_options(synchronize_session=False),
    ):
        raise unlisted
    session.refresh(person)
    audit.write_event(
        session,
        event_type="person.revoked",
        actor=actor.person,
        refs={"person_id": person.id},
        reason=reason,
    )


def promote(session: Session, actor: Actor, person: Person) -> None:
    """Make `person` an Admin (segment AD2M), putting them on the operator
    list if they are not on it. Only someone bound to an account."""
    if not makes_admins(session, actor):
        raise Refused("Only the platform super-admin makes Admins.", key="not_super_admin")
    if not person.bound:
        raise Refused("Only someone who has signed in can be an Admin.", key="pending")
    already = Refused("Already an Admin.", key="already_admin")
    session.refresh(person, attribute_names=["is_admin", "may_operate", "revoked_at"])
    if person.is_admin:
        raise already
    listed = may_operate(person)
    values: dict[str, Any] = {"is_admin": True}
    if not listed:
        values |= {
            "may_operate": True,
            "admitted_by_id": actor.person.id if actor.person is not None else None,
            "admitted_at": _now(),
            "revoked_at": None,
        }
    # Conditional, as `admit`: of two promotions at once one is audited.
    if not _changed(
        session,
        update(Person)
        .where(Person.id == person.id, Person.is_admin.is_(False))
        .values(**values)
        .execution_options(synchronize_session=False),
    ):
        raise already
    session.refresh(person)
    if not listed:
        audit.write_event(
            session, event_type="person.admitted", actor=actor.person, refs={"person_id": person.id}
        )
    audit.write_event(
        session, event_type="person.promoted", actor=actor.person, refs={"person_id": person.id}
    )


def demote(session: Session, actor: Actor, person: Person) -> None:
    """Take `person`'s Admin away (segment AD2M); they stay on the operator
    list. With no super-admin configured, the last Admin is kept."""
    if not makes_admins(session, actor):
        raise Refused("Only the platform super-admin makes Admins.", key="not_super_admin")
    not_admin = Refused("Not an Admin.", key="not_admin")
    session.refresh(person, attribute_names=["is_admin"])
    if not person.is_admin:
        raise not_admin
    if not super_admin_configured():
        # Every Admin row locked before counting, so two demotions at once
        # cannot both see another Admin left (Review Robin's last_admin).
        admins = session.scalars(
            select(Person.id).where(Person.is_admin.is_(True)).with_for_update()
        ).all()
        if len(admins) <= 1:
            raise Refused("The last Admin stays an Admin.", key="last_admin")
    if not _changed(
        session,
        update(Person)
        .where(Person.id == person.id, Person.is_admin.is_(True))
        .values(is_admin=False)
        .execution_options(synchronize_session=False),
    ):
        raise not_admin
    session.refresh(person)
    audit.write_event(
        session, event_type="person.demoted", actor=actor.person, refs={"person_id": person.id}
    )


# --------------------------------------------------------------------------- #
# An exercise's operators
# --------------------------------------------------------------------------- #


def create_exercise(session: Session, actor: Actor, public_id: str) -> Exercise:
    """Make an exercise's row with `actor` its Owner, in one transaction.
    The actor needs a person row and must be allowlisted, or be the
    platform super-admin, who needs no allowlisting (ruling 75)."""
    if actor.person is None or not (
        actor.is_super_admin or _allowed(session, actor.person, hold=True)
    ):
        raise Refused("Only someone on the operator list may make an exercise.", key="not_listed")
    exercise = Exercise(public_id=public_id)
    session.add(exercise)
    session.flush()
    session.add(ExerciseOperator(exercise_id=exercise.id, person_id=actor.person.id, is_owner=True))
    session.flush()
    audit.write_event(
        session,
        event_type="exercise.created",
        actor=actor.person,
        exercise=exercise,
        refs={"owner_id": actor.person.id},
    )
    return exercise


def add_operator(session: Session, exercise: Exercise, actor: Actor, person: Person) -> None:
    """Add `person` as an operator; only the Owner (or the super-admin)."""
    _lock(session, exercise)
    if not _is_owner(session, exercise, actor):
        raise Refused("Only the exercise's Owner adds operators.", key="not_owner")
    if not _allowed(session, person, hold=True):
        raise Refused("Only someone on the operator list can be added.", key="not_listed")
    grant = _grant(session, exercise, person)
    if grant is not None and grant.removed_at is None:
        raise Refused("Already an operator.", key="already_operator")
    readded = grant is not None
    if grant is None:
        grant = ExerciseOperator(exercise_id=exercise.id, person_id=person.id)
        session.add(grant)
    grant.is_owner = False
    grant.removed_at = None
    grant.added_by_id = actor.person.id if actor.person is not None else None
    grant.added_at = _now()
    session.flush()
    audit.write_event(
        session,
        event_type="exercise.operator_added",
        actor=actor.person,
        exercise=exercise,
        refs={"person_id": person.id},
        context={"readded": readded},
    )


def remove_operator(session: Session, exercise: Exercise, actor: Actor, person: Person) -> None:
    """Remove `person`; only the Owner (or the super-admin), and never the
    Owner themself."""
    _lock(session, exercise)
    if not _is_owner(session, exercise, actor):
        raise Refused("Only the exercise's Owner removes operators.", key="not_owner")
    grant = _grant(session, exercise, person)
    if grant is None or grant.removed_at is not None:
        raise Refused("Not an operator of this exercise.", key="not_operator")
    if grant.is_owner:
        raise Refused("The Owner cannot be removed; hand ownership over first.", key="is_owner")
    removed = _changed(
        session,
        update(ExerciseOperator)
        .where(
            ExerciseOperator.id == grant.id,
            ExerciseOperator.removed_at.is_(None),
            ExerciseOperator.is_owner.is_(False),
        )
        .values(removed_at=_now())
        .execution_options(synchronize_session=False),
    )
    session.expire(grant)
    if not removed:  # made the Owner, or removed, meanwhile
        raise Refused(
            "They have just become the Owner or been removed; reload and try again.", key="changed"
        )
    audit.write_event(
        session,
        event_type="exercise.operator_removed",
        actor=actor.person,
        exercise=exercise,
        refs={"person_id": person.id},
    )


def hand_over(session: Session, exercise: Exercise, actor: Actor, person: Person) -> None:
    """Make `person`, a current allowlisted operator, an Owner in the
    actor's place; the actor stays an operator. Only an Owner."""
    _lock(session, exercise)
    if not _is_owner(session, exercise, actor):
        raise Refused("Only the exercise's Owner hands ownership over.", key="not_owner")
    if not _allowed(session, person, hold=True):
        raise Refused("Only someone on the operator list can own an exercise.", key="not_listed")
    grant = _grant(session, exercise, person)
    if grant is None or grant.removed_at is not None:
        raise Refused("Add them as an operator first.", key="not_operator")
    if grant.is_owner:
        raise Refused("Already the Owner.", key="already_owner")
    # The Owner handing over steps down: the actor's own grant (the
    # platform, acting as no one, hands over the first Owner's).
    former = session.scalar(
        select(ExerciseOperator)
        .where(
            ExerciseOperator.exercise_id == exercise.id,
            ExerciseOperator.is_owner.is_(True),
            ExerciseOperator.removed_at.is_(None),
            *(() if actor.person is None else (ExerciseOperator.person_id == actor.person.id,)),
        )
        .order_by(ExerciseOperator.id)
        .limit(1)
        .execution_options(populate_existing=True)
    )
    if former is None and actor.person is not None:
        # The actor's own Owner row is gone: their check passed just before
        # ownership moved elsewhere, so nothing is changed (Codex on #4110).
        raise Refused("Ownership has just changed; reload and try again.", key="changed")
    # Each step restates its rule in its WHERE: the former Owner is still
    # an Owner, and the new one is still a current operator.
    if former is not None and not _changed(
        session,
        update(ExerciseOperator)
        .where(
            ExerciseOperator.id == former.id,
            ExerciseOperator.is_owner.is_(True),
            # The Owner demoted is the one whose authority was checked
            # (Codex on #4110).
            *(() if actor.person is None else (ExerciseOperator.person_id == actor.person.id,)),
        )
        .values(is_owner=False)
        .execution_options(synchronize_session=False),
    ):
        raise Refused("Ownership has just changed; reload and try again.", key="changed")
    if not _changed(
        session,
        update(ExerciseOperator)
        .where(ExerciseOperator.id == grant.id, ExerciseOperator.removed_at.is_(None))
        .values(is_owner=True)
        .execution_options(synchronize_session=False),
    ):
        raise Refused("They have just been removed; reload and try again.", key="changed")
    former_person_id = former.person_id if former is not None else None
    for row in (grant, former):
        if row is not None:
            session.expire(row)
    refs = {"person_id": person.id}
    if former_person_id is not None:
        refs["former_owner_id"] = former_person_id
    audit.write_event(
        session,
        event_type="exercise.ownership_handed_over",
        actor=actor.person,
        exercise=exercise,
        refs=refs,
    )


def adopt(session: Session, exercise: Exercise, actor: Actor) -> bool:
    """Make `actor`, an Admin or the super-admin, an Owner of `exercise`
    (segment AD2M, `applydesk/spec/permissions.md` §5): the one way either
    takes up an exercise, so every change has an Owner on record. True if
    it changed anything; adopting one already owned changes nothing."""
    _lock(session, exercise)
    if actor.person is None or not (actor.is_super_admin or _admin_now(session, actor.person)):
        raise Refused("Only an Admin or the platform super-admin adopts.", key="not_admin")
    grant = _grant(session, exercise, actor.person)
    if grant is not None and grant.removed_at is None and grant.is_owner:
        return False
    was = "none" if grant is None else ("removed" if grant.removed_at else "operator")
    if grant is None:
        grant = ExerciseOperator(exercise_id=exercise.id, person_id=actor.person.id)
        session.add(grant)
    grant.is_owner = True
    grant.removed_at = None
    grant.added_by_id = actor.person.id
    grant.added_at = _now()
    session.flush()
    audit.write_event(
        session,
        event_type="exercise.adopted",
        actor=actor.person,
        exercise=exercise,
        refs={"person_id": actor.person.id},
        context={"was": was},
    )
    return True
