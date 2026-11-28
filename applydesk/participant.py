"""The signed-in person on the participant's pages, `/me/…` (segment AD4A):
who they are, their own applications, and the exercises open to them.
Each reads in a session of its own, as the pages hand none."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select

from applydesk import applications, db, eligibility, locks, people, sample_data
from applydesk.eligibility import Reason
from applydesk.models import Application, Exercise
from cordware.identity import Identity

#: What shows on /me (ruling 41): a Closed exercise stays, read-only, with
#: its released results; Draft and Archived do not. "Completed" is a status
#: worked out from stages (`locks.exercise_status`) for an exercise made with
#: *New exercise*: one whose stages have all completed stays, as a Closed
#: one does (segment AD4A).
ON_ME = ("Published", "Completed", "Closed")


def signed_in(identity: Identity | None) -> int | None:
    """The signed-in person's row ID, bound to their account as the
    operator pages bind it (`people.resolve`); None for no one signed in,
    or an identity that cannot be bound."""
    if identity is None:
        return None
    session = db.new_session()
    try:
        person = people.resolve(session, identity)
        session.commit()
        return person.id if person is not None else None
    finally:
        session.close()


def my_applications(person_id: int | None) -> tuple[sample_data.Application, ...]:
    """The person's own applications, in every exercise, drafts included,
    in the order they were started; none for no one."""
    if person_id is None:
        return ()
    session = db.new_session()
    try:
        ids = tuple(
            session.scalars(
                select(Application.public_id)
                .where(Application.person_id == person_id)
                .order_by(Application.id)
            )
        )
    finally:
        session.close()
    return applications.with_ids(ids) if ids else ()


def owns(person_id: int | None, application_id: str) -> bool:
    """Whether the application is the person's own."""
    if person_id is None:
        return False
    session = db.new_session()
    try:
        found = session.scalar(
            select(Application.person_id).where(Application.public_id == application_id)
        )
    finally:
        session.close()
    return found == person_id


def open_to(
    person_id: int | None, shown: Iterable[sample_data.Exercise]
) -> tuple[tuple[sample_data.Exercise, Reason], ...]:
    """Of ``shown``, each exercise whose Form admits the person, with why
    (`eligibility.may_apply`), in the order given."""
    if person_id is None:
        return ()
    session = db.new_session()
    try:
        person = session.get(people.Person, person_id)
        rows = {
            row.public_id: row
            for row in session.scalars(
                select(Exercise).where(Exercise.public_id.in_([e.public_id for e in shown]))
            )
        }
        out: list[tuple[sample_data.Exercise, Reason]] = []
        for e in shown:
            row = rows.get(e.public_id)
            why = eligibility.may_apply(session, row, person) if row is not None else None
            if why is not None:
                out.append((e, why))
        return tuple(out)
    finally:
        session.close()


def archived_ids(public_ids: Iterable[str]) -> frozenset[str]:
    """Of these exercises, the archived ones (`archived_at`), which /me
    never shows (ruling 41), whatever their state reads."""
    ids = list(public_ids)
    if not ids:
        return frozenset()
    session = db.new_session()
    try:
        return frozenset(
            session.scalars(
                select(Exercise.public_id).where(
                    Exercise.public_id.in_(ids), Exercise.archived_at.is_not(None)
                )
            )
        )
    finally:
        session.close()


def on_me(e: sample_data.Exercise, archived: frozenset[str]) -> bool:
    """Whether the exercise shows on /me (ruling 41): never archived; a
    sample by its own state; an exercise made with *New exercise*, whose
    state stays Draft, by its status as its stages give it, so it shows
    once published. The status is the costly part, so it comes last."""
    if e.public_id in archived:
        return False
    if sample_data.is_sample(e.public_id):
        return e.state in ON_ME
    return locks.exercise_status(e) in ON_ME


def lobby(
    person_id: int | None, live: Iterable[sample_data.Exercise]
) -> tuple[tuple[tuple[sample_data.Exercise, Reason], ...], tuple[sample_data.Application, ...]]:
    """The User Lobby's *Open to me* (each exercise on /me whose Form admits
    the person, with why) and *My applications* (their own, in exercises
    not deleted or archived). Who may apply is checked before the status,
    so the stages of an exercise the person cannot apply to are not read."""
    live = tuple(live)
    archived = archived_ids(e.public_id for e in live)
    kept = [e for e in live if e.public_id not in archived]
    admitted = tuple(pair for pair in open_to(person_id, kept) if on_me(pair[0], archived))
    shown = {e.public_id for e in kept}
    mine = tuple(a for a in my_applications(person_id) if a.exercise_id in shown)
    return admitted, mine


def may_see(person_id: int | None, e: sample_data.Exercise) -> bool:
    """Whether the person reaches the exercise's /me page: it shows on /me,
    and its Form admits them or they have an application in it (segment
    AD4A; the series' rule, checked on the server)."""
    if not on_me(e, archived_ids([e.public_id])):
        return False
    if open_to(person_id, [e]):
        return True
    return any(a.exercise_id == e.public_id for a in my_applications(person_id))
