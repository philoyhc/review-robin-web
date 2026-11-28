"""Who may apply (segment AD4A; ruling 84): `eligibility.may_apply` follows
the Form's *Who may apply* as stored: anyone signed in, the invite list, or
the people Create dossiers holds a dossier for."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from applydesk import candidates, db, eligibility, exercises, invitees, operators, people
from applydesk.models import Exercise, Person
from applydesk.models import Stage as StageRow

pytestmark = pytest.mark.usefixtures("applydesk_db")


def _exercise(eligibility_: str | None = None, *, create_dossiers: bool = False) -> str:
    session = db.new_session()
    owner = session.scalars(select(Person).where(Person.may_operate)).first()
    assert owner is not None
    made = exercises.make(session, operators.Actor(owner), "Who may apply")
    row = session.scalars(select(Exercise).where(Exercise.public_id == made.public_id)).one()
    row.eligibility = eligibility_
    session.add(
        StageRow(
            exercise_id=row.id,
            key="s1",
            position=1,
            holds_form=not create_dossiers,
            holds_candidates=create_dossiers,
        )
    )
    if create_dossiers:
        session.add(StageRow(exercise_id=row.id, key="s2", position=2, holds_form=True))
    session.commit()
    public_id = row.public_id
    session.close()
    return public_id


def _why(public_id: str, address: str | None) -> str | None:
    session = db.new_session()
    try:
        row = session.scalars(select(Exercise).where(Exercise.public_id == public_id)).one()
        person = people.pending(session, address, None) if address else None
        return eligibility.may_apply(session, row, person)
    finally:
        session.rollback()
        session.close()


def _add(public_id: str, address: str, svc: object) -> None:
    """Put ``address`` on the invite list or Create dossiers' entries."""
    session = db.new_session()
    person = people.pending(session, address, None)
    if svc is invitees:
        invitees.add(session, public_id, person, "search", None)
    else:
        candidates.add(session, public_id, person, "search", None)
    session.commit()
    session.close()


@pytest.mark.parametrize("stored", ["open", None])
def test_anyone_signed_in_may_apply(stored: str | None) -> None:
    ex = _exercise(stored)
    assert _why(ex, "ann@example.edu") == "open"


def test_no_one_signed_in_may_not() -> None:
    assert _why(_exercise("open"), None) is None


def test_invitees_only_the_invited_and_not_once_removed() -> None:
    ex = _exercise("invitation")
    _add(ex, "ann@example.edu", invitees)
    assert _why(ex, "ann@example.edu") == "invited"
    assert _why(ex, "bob@example.edu") is None
    session = db.new_session()
    entry = invitees.listing(session, ex)[0].id
    invitees.remove(session, ex, entry, None)
    session.commit()
    session.close()
    assert _why(ex, "ann@example.edu") is None


def test_create_dossiers_admits_the_people_it_holds_dossiers_for() -> None:
    """With Create dossiers on the timeline the Form writes to its dossiers
    (ruling 83), whatever the stored eligibility says."""
    ex = _exercise("invitation", create_dossiers=True)
    _add(ex, "ann@example.edu", candidates)
    assert _why(ex, "ann@example.edu") == "dossier"
    assert _why(ex, "bob@example.edu") is None
    session = db.new_session()
    candidates.remove(session, ex, candidates.listing(session, ex)[0].id, None)
    session.commit()
    session.close()
    assert _why(ex, "ann@example.edu") is None


def test_an_archived_exercise_admits_no_one() -> None:
    ex = _exercise("open")
    session = db.new_session()
    row = session.scalars(select(Exercise).where(Exercise.public_id == ex)).one()
    row.archived_at = datetime.now(UTC)
    session.commit()
    session.close()
    assert _why(ex, "ann@example.edu") is None
