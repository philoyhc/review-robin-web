"""The row locks AD2O's moves rely on, which SQLite cannot show (AD-128,
segment AD2C): on Postgres, while one session holds an exercise's lock, a
second session's ownership move or Revoke waits on it. Each wait is cut
short by a ``lock_timeout``, so the test sees the block rather than hangs.
Skipped on SQLite, where the whole file is the lock."""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from applydesk import db, operators, people
from applydesk.models import Exercise, Person
from applydesk.operators import Actor
from cordware.identity import Identity

pytestmark = pytest.mark.usefixtures("unseeded")

SUPER = Actor(person=None, is_super_admin=True, platform=True)


@pytest.fixture
def session(applydesk_db: None) -> Iterator[Session]:
    if db.engine().dialect.name != "postgresql":
        pytest.skip("row locks: Postgres only (TEST_DATABASE_URL, ci-postgres)")
    s = db.new_session()
    yield s
    s.close()


def _person(session: Session, oid: str) -> Person:
    person = people.resolve(
        session, Identity(principal_id=oid, email=f"{oid}@x.edu", name=oid, tenant_id="t")
    )
    assert person is not None
    operators.admit(session, SUPER, person)
    session.flush()
    return person


def _blocked_by_the_lock(
    holder: Session, exercise: Exercise, move: Callable[[Session], None]
) -> None:
    """``move(other, exercise_there, ...)`` run in a second session while
    ``holder`` holds the exercise's row lock: it must wait, so it times out."""
    operators._lock(holder, exercise)  # pyright: ignore[reportPrivateUsage]  -- the lock under test
    other = db.new_session()
    try:
        other.execute(text("SET lock_timeout = '300ms'"))
        with pytest.raises(OperationalError, match="lock timeout"):
            move(other)
    finally:
        other.rollback()
        other.close()
        holder.rollback()


def test_a_step_down_waits_on_the_exercise_lock(session: Session) -> None:
    ann, ben = _person(session, "ann"), _person(session, "ben")
    exercise = operators.create_exercise(session, Actor(ann), "ex0000lck1")
    operators.add_operator(session, exercise, Actor(ann), ben)
    operators.make_owner(session, exercise, Actor(ann), ben)
    session.commit()
    ids = (exercise.id, ann.id)

    def step_down(other: Session) -> None:
        there = other.get(Exercise, ids[0])
        me = other.get(Person, ids[1])
        assert there is not None and me is not None
        operators.demote_owner(other, there, Actor(me), me)

    _blocked_by_the_lock(session, exercise, step_down)


def test_revoke_waits_on_the_lock_of_an_exercise_it_owns(session: Session) -> None:
    """Revoke locks each live exercise the person owns before counting its
    Owners (AD2O, Codex on #4145)."""
    ann, ben = _person(session, "ann"), _person(session, "ben")
    exercise = operators.create_exercise(session, Actor(ann), "ex0000lck2")
    operators.add_operator(session, exercise, Actor(ann), ben)
    operators.make_owner(session, exercise, Actor(ann), ben)
    session.commit()
    ben_id = ben.id

    def revoke(other: Session) -> None:
        target = other.get(Person, ben_id)
        assert target is not None
        operators.revoke(other, SUPER, target)

    _blocked_by_the_lock(session, exercise, revoke)
