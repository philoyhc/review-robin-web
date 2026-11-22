"""An exercise's Operators card, wired (segment AD2A, rung 8; ruling 73):
who operates it, and the Owner's changes, for `routes_operator.py`.

The Owner, or the platform super-admin, adds operators found among the
operator list (`directory.search`, `allowlist_only`), removes them and
hands ownership over; everyone else sees the card read-only. Every change
is `operators.add_operator`, `remove_operator` or `hand_over`, which lock
the exercise, check on fresh rows and audit. A refusal raises
`operators.Refused`.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from applydesk import directory, operators, people
from applydesk.models import Exercise, Person
from cordware.identity import Identity


@dataclass(frozen=True)
class Card:
    """What the card shows: each current operator and whether they are the
    Owner (the Owner first), whether the viewer may change them, and
    whether the exercise has a row at all (a sample not yet seeded has
    none, and so no operators)."""

    rows: list[tuple[Person, bool]]
    manage: bool
    recorded: bool
    viewer_id: int | None = None  # the viewer's own row, for Step down and Leave (AD2O)

    @property
    def owners(self) -> int:
        """How many Owners: the last one cannot step down (AD2O)."""
        return sum(1 for _, owner in self.rows if owner)


def actor_for(session: Session, identity: Identity) -> operators.Actor:
    return operators.Actor(people.resolve(session, identity), identity.is_super_admin)


def _exercise(session: Session, public_id: str) -> Exercise | None:
    # A deleted exercise's operators are not changed (cold read, AD2B).
    return session.scalar(
        select(Exercise).where(Exercise.public_id == public_id, Exercise.deleted_at.is_(None))
    )


def card(session: Session, public_id: str, identity: Identity | None) -> Card:
    exercise = _exercise(session, public_id)
    if exercise is None:
        return Card([], False, False)
    rows = operators.current_operators(session, exercise)
    actor = actor_for(session, identity) if identity is not None else None
    manage = actor is not None and operators.is_owner(session, exercise, actor)
    viewer_id = actor.person.id if actor is not None and actor.person is not None else None
    return Card(rows, manage, True, viewer_id)


def candidates(session: Session, public_id: str, query: str) -> list[Person]:
    """People on the operator list matching `query`, less the exercise's
    current operators: whom the Owner may add."""
    exercise = _exercise(session, public_id)
    current: frozenset[int] = frozenset()
    if exercise is not None:
        current = frozenset(p.id for p, _ in operators.current_operators(session, exercise))
    # Left out in the search, before its limit: filtering after it could
    # leave nobody to add (bug sweep at the AD2A close).
    found = directory.search(session, query, None, allowlist_only=True, exclude=current)
    return list(found.on_record)


def _target(session: Session, public_id: str, person_id: int) -> tuple[Exercise, Person]:
    exercise = _exercise(session, public_id)
    person = session.get(Person, person_id)
    if exercise is None or person is None:
        raise operators.Refused("That exercise or person is no longer on record.", key="gone")
    return exercise, person


def add(session: Session, public_id: str, identity: Identity, person_id: int) -> None:
    exercise, person = _target(session, public_id, person_id)
    operators.add_operator(session, exercise, actor_for(session, identity), person)


def remove(session: Session, public_id: str, identity: Identity, person_id: int) -> None:
    exercise, person = _target(session, public_id, person_id)
    operators.remove_operator(session, exercise, actor_for(session, identity), person)


def make_owner(session: Session, public_id: str, identity: Identity, person_id: int) -> None:
    exercise, person = _target(session, public_id, person_id)
    operators.hand_over(session, exercise, actor_for(session, identity), person)
