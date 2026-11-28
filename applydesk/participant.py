"""The signed-in person on the participant's pages, `/me/…` (segment AD4A):
who they are, their own applications, and the exercises open to them.
Each reads in a session of its own, as the pages hand none."""

from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select

from applydesk import applications, db, eligibility, people, sample_data
from applydesk.eligibility import Reason
from applydesk.models import Application, Exercise
from cordware.identity import Identity


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
