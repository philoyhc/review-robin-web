"""A Form's invitees (ruling 84, segment AD2I): the people who may submit
when the Form's *Who may apply* is *Invitees*, added through the people
search (ruling 75) or a CSV upload, removed in the list. Each may submit
up to the exercise's dossiers per person, their dossiers made only as they
submit (AD4), so none is made in advance.

A person is listed once per exercise (``uq_invitee_pair``). Removing
someone sets ``removed_at``; adding them again clears it on the same row.
A CSV saves its good rows and lists the rest back, as Create dossiers'
does: each row is one address and, if given, a name. Each add and removal
is audited. The list is kept as each change is made, not by Process's Save.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from applydesk import audit, candidates, db
from applydesk.candidates import Imported, Listed, Refused
from applydesk.models import Exercise, Invitee, Person, Stage

__all__ = [
    "Imported",
    "Listed",
    "Refused",
    "add",
    "already",
    "full",
    "import_csv",
    "listing",
    "remove",
    "tab_shown",
]


def listing(session: Session, public_id: str) -> tuple[Listed, ...]:
    """The exercise's current invitees, in the order they were added."""
    exercise = session.scalar(select(Exercise).where(Exercise.public_id == public_id))
    if exercise is None:
        return ()
    rows = session.execute(
        select(Invitee, Person)
        .join(Person, Person.id == Invitee.person_id)
        .where(Invitee.exercise_id == exercise.id, Invitee.removed_at.is_(None))
        .order_by(Invitee.added_at, Invitee.id)
    )
    return tuple(
        Listed(
            i.id,
            p.id,
            p.display_name or "",
            p.email or "",
            i.via,
            i.added_at,
            verified=p.object_id is not None,
        )
        for i, p in rows
    )


def full(session: Session, public_id: str) -> frozenset[int]:
    """The people already invited: the search leaves them out."""
    return frozenset(i.person_id for i in listing(session, public_id))


def add(session: Session, public_id: str, person: Person, via: str, actor: Person | None) -> bool:
    """Invite ``person``; False if they were invited already. Flushes."""
    if via not in candidates.VIA:
        raise ValueError(via)
    exercise = candidates.exercise_row(session, public_id)
    row = session.scalar(
        select(Invitee).where(Invitee.exercise_id == exercise.id, Invitee.person_id == person.id)
    )
    now = datetime.now(UTC)
    if row is not None and row.removed_at is None:
        return False
    if row is not None:  # removed before: invited again on the same row
        row.removed_at, row.via, row.added_by_id, row.added_at = (
            None,
            via,
            actor.id if actor else None,
            now,
        )
    else:
        try:
            with session.begin_nested():
                row = Invitee(
                    exercise_id=exercise.id,
                    person_id=person.id,
                    via=via,
                    added_by_id=actor.id if actor else None,
                    added_at=now,
                )
                session.add(row)
        except IntegrityError:
            return False  # another request invited them meanwhile
    session.flush()
    audit.write_event(
        session,
        event_type="invitee.added",
        actor=actor,
        exercise=exercise,
        refs={"person_id": person.id},
        context={"via": via},
    )
    return True


def remove(session: Session, public_id: str, entry_id: int, actor: Person | None) -> bool:
    """Take one invitee off the list by their row; False if not on it."""
    exercise = candidates.exercise_row(session, public_id)
    row = session.scalar(
        select(Invitee).where(
            Invitee.exercise_id == exercise.id,
            Invitee.id == entry_id,
            Invitee.removed_at.is_(None),
        )
    )
    if row is None:
        return False
    row.removed_at = datetime.now(UTC)
    session.flush()
    audit.write_event(
        session,
        event_type="invitee.removed",
        actor=actor,
        exercise=exercise,
        refs={"person_id": row.person_id},
    )
    return True


def import_csv(session: Session, public_id: str, text: str, actor: Person | None) -> Imported:
    """Invite each good row of a CSV with an *Email* column and, if given,
    a *Name* one; the rest are listed back by row number. A person twice in
    the file is listed back. Flushes; the caller commits."""
    return candidates.read_csv(
        session,
        public_id,
        text,
        actor,
        most=1,
        add=lambda person, title: add(session, public_id, person, "csv", actor),
    )


def already(session: Session, public_id: str) -> str:
    """What an add of someone already invited says."""
    return "Already invited."


def tab_shown(public_id: str) -> bool:
    """Whether the Invitees tab shows (segment AD2N): the Form's *Who may
    apply* is *Invitees* as saved, and no Create dossiers is on the
    timeline (with one, the Form invites from its dossiers). Read in a
    session of its own, as the chrome is drawn."""
    session = db.new_session()
    try:
        exercise = session.scalar(select(Exercise).where(Exercise.public_id == public_id))
        if exercise is None or exercise.eligibility != "invitation":
            return False
        held = session.scalar(
            select(Stage.id).where(
                Stage.exercise_id == exercise.id,
                Stage.retired_at.is_(None),
                Stage.holds_candidates.is_(True),
            )
        )
        return held is None
    finally:
        session.close()
