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

Each change is audited in the same transaction. A refusal raises
`Refused`, its message the rule, fit to show. Functions flush; the caller
commits.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from applydesk import audit
from applydesk.models import Exercise, ExerciseOperator, Person


class Refused(Exception):
    """A change the rules do not allow; the message says which."""


@dataclass(frozen=True)
class Actor:
    """Who is acting: their person (None for a super-admin with no row
    yet) and whether they are the platform super-admin."""

    person: Person | None
    is_super_admin: bool = False


def _now() -> datetime:
    return datetime.now(UTC)


def may_operate(person: Person | None) -> bool:
    """On the allowlist and not revoked."""
    return person is not None and person.may_operate and person.revoked_at is None


def _grant(session: Session, exercise: Exercise, person: Person) -> ExerciseOperator | None:
    return session.scalar(
        select(ExerciseOperator).where(
            ExerciseOperator.exercise_id == exercise.id, ExerciseOperator.person_id == person.id
        )
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


def owner_of(session: Session, exercise: Exercise) -> Person | None:
    return session.scalar(
        select(Person)
        .join(ExerciseOperator, ExerciseOperator.person_id == Person.id)
        .where(
            ExerciseOperator.exercise_id == exercise.id,
            ExerciseOperator.is_owner.is_(True),
            ExerciseOperator.removed_at.is_(None),
        )
    )


def can_operate(session: Session, exercise: Exercise, actor: Actor) -> bool:
    """Whether `actor` reaches `exercise`: the super-admin always; anyone
    else on the allowlist with a current grant."""
    if actor.is_super_admin:
        return True
    if not may_operate(actor.person):
        return False
    assert actor.person is not None
    grant = _grant(session, exercise, actor.person)
    return grant is not None and grant.removed_at is None


def operated_exercises(session: Session, actor: Actor) -> list[Exercise]:
    """The exercises `actor` reaches: every one for the super-admin."""
    if actor.is_super_admin:
        return list(session.scalars(select(Exercise).order_by(Exercise.id)))
    if not may_operate(actor.person):
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


def _is_owner(session: Session, exercise: Exercise, actor: Actor) -> bool:
    if actor.is_super_admin:
        return True
    owner = owner_of(session, exercise)
    return (
        actor.person is not None
        and owner is not None
        and owner.id == actor.person.id
        and may_operate(actor.person)
    )


# --------------------------------------------------------------------------- #
# The allowlist: the platform super-admin's
# --------------------------------------------------------------------------- #


def admit(session: Session, actor: Actor, person: Person) -> None:
    """Put `person` on the allowlist (ruling 75)."""
    if not actor.is_super_admin:
        raise Refused("Only the platform super-admin keeps the operator list.")
    if may_operate(person):
        raise Refused("Already allowed to operate.")
    person.may_operate = True
    person.admitted_by_id = actor.person.id if actor.person is not None else None
    person.admitted_at = _now()
    person.revoked_at = None
    session.flush()
    audit.write_event(
        session, event_type="person.admitted", actor=actor.person, refs={"person_id": person.id}
    )


def revoke(session: Session, actor: Actor, person: Person, reason: str | None = None) -> None:
    """Take `person` off the allowlist: their access ends, their grants are
    kept (re-admitting restores them)."""
    if not actor.is_super_admin:
        raise Refused("Only the platform super-admin keeps the operator list.")
    if not may_operate(person):
        raise Refused("Not on the operator list.")
    person.may_operate = False
    person.revoked_at = _now()
    session.flush()
    audit.write_event(
        session,
        event_type="person.revoked",
        actor=actor.person,
        refs={"person_id": person.id},
        reason=reason,
    )


# --------------------------------------------------------------------------- #
# An exercise's operators
# --------------------------------------------------------------------------- #


def create_exercise(session: Session, actor: Actor, public_id: str) -> Exercise:
    """Make an exercise's row with `actor` its Owner, in one transaction.
    The actor must be allowlisted and have a person row."""
    if actor.person is None or not may_operate(actor.person):
        raise Refused("Only someone on the operator list may make an exercise.")
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
    if not _is_owner(session, exercise, actor):
        raise Refused("Only the exercise's Owner adds operators.")
    if not may_operate(person):
        raise Refused("Only someone on the operator list can be added.")
    grant = _grant(session, exercise, person)
    if grant is not None and grant.removed_at is None:
        raise Refused("Already an operator.")
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
    if not _is_owner(session, exercise, actor):
        raise Refused("Only the exercise's Owner removes operators.")
    grant = _grant(session, exercise, person)
    if grant is None or grant.removed_at is not None:
        raise Refused("Not an operator of this exercise.")
    if grant.is_owner:
        raise Refused("The Owner cannot be removed; hand ownership over first.")
    grant.removed_at = _now()
    session.flush()
    audit.write_event(
        session,
        event_type="exercise.operator_removed",
        actor=actor.person,
        exercise=exercise,
        refs={"person_id": person.id},
    )


def hand_over(session: Session, exercise: Exercise, actor: Actor, person: Person) -> None:
    """Make `person`, a current allowlisted operator, the Owner; the former
    Owner stays an operator. Only the Owner (or the super-admin)."""
    if not _is_owner(session, exercise, actor):
        raise Refused("Only the exercise's Owner hands ownership over.")
    if not may_operate(person):
        raise Refused("Only someone on the operator list can own an exercise.")
    grant = _grant(session, exercise, person)
    if grant is None or grant.removed_at is not None:
        raise Refused("Add them as an operator first.")
    if grant.is_owner:
        raise Refused("Already the Owner.")
    former = session.scalar(
        select(ExerciseOperator).where(
            ExerciseOperator.exercise_id == exercise.id,
            ExerciseOperator.is_owner.is_(True),
            ExerciseOperator.removed_at.is_(None),
        )
    )
    if former is not None:
        former.is_owner = False
    grant.is_owner = True
    session.flush()
    refs = {"person_id": person.id}
    if former is not None:
        refs["former_owner_id"] = former.person_id
    audit.write_event(
        session,
        event_type="exercise.ownership_handed_over",
        actor=actor.person,
        exercise=exercise,
        refs=refs,
    )
