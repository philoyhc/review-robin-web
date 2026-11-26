"""An exercise's applications (segment AD2J; AD-38), kept in the
`application` table: each one's applicant a person (ruling 73), its state
`draft`, `submitted` or `withdrawn`, and the time of each move.

Applicants submit from AD4. Until then the only applications are the
samples', which the localhost seed records (ruling 74)."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from applydesk import audit, db, people, sample_data
from applydesk.models import Application, Dossier, Exercise, Person

#: A sample's state, as `sample_data` words it, and the stored one.
_STATES = {"Draft": "draft", "Submitted": "submitted", "Withdrawn": "withdrawn"}
_SAID = {stored: said for said, stored in _STATES.items()}


def day(when: datetime) -> str:
    """A stored time as the pages show an application's day (``3 Sep
    2026``), in UTC, where the samples' noon keeps it."""
    return f"{when.astimezone(UTC):%d %b %Y}".lstrip("0")


def from_row(
    row: Application, person: Person, exercise_id: str, dossier_id: str | None
) -> sample_data.Application:
    """A stored application in the shape the pages read."""
    started = row.started_at.replace(tzinfo=row.started_at.tzinfo or UTC)
    submitted = (
        row.submitted_at.replace(tzinfo=row.submitted_at.tzinfo or UTC)
        if row.submitted_at is not None
        else None
    )
    return sample_data.Application(
        public_id=row.public_id,
        exercise_id=exercise_id,
        applicant=row.name,
        email=person.email or "",
        title=row.title,
        state=_SAID[row.state],
        submitted=day(submitted or started),
        dossier_id=dossier_id or "",
        started_at=started,
        submitted_at=submitted,
    )


def _read(
    query: Select[Application, Person, str, str],
) -> tuple[sample_data.Application, ...]:
    session = db.new_session()
    try:
        return tuple(
            from_row(row, person, exercise_id, dossier_id)
            for row, person, exercise_id, dossier_id in session.execute(query)
        )
    finally:
        session.close()


def _query() -> Select[Application, Person, str, str]:
    return (
        select(Application, Person, Exercise.public_id, Dossier.public_id)
        .join(Person, Person.id == Application.person_id)
        .outerjoin(Dossier, Dossier.application_id == Application.id)
        .join(Exercise, Exercise.id == Application.exercise_id)
        .order_by(Application.id)
    )


def of(exercise_id: str) -> tuple[sample_data.Application, ...]:
    """The exercise's applications, in the order they came in, read in a
    session of their own (the readers in `sample_data`, which no route hands
    a session); none for an exercise not on record."""
    return _read(_query().where(Exercise.public_id == exercise_id))


def with_ids(public_ids: Iterable[str]) -> tuple[sample_data.Application, ...]:
    """The applications with these public IDs, wherever they are."""
    return _read(_query().where(Application.public_id.in_(list(public_ids))))


def sample_day(text: str) -> datetime:
    """A sample's day (``"3 Sep 2026"``) as a time: noon UTC, which keeps
    its date in every zone from UTC-11 to UTC+11."""
    day = datetime.strptime(text, "%d %b %Y")
    return day.replace(hour=12, tzinfo=UTC)


def record_samples(
    session: Session,
    exercise: Exercise,
    samples: tuple[sample_data.Application, ...],
    actor: Person | None,
) -> int:
    """Record `samples` on `exercise` (the seed), in their order; one
    already on record is left alone. Each applicant is the pending person
    of their address, as Candidates' CSV makes them. Returns how many were
    added, and audits them as one event when any were."""
    known = set(
        session.scalars(select(Application.public_id).where(Application.exercise_id == exercise.id))
    )
    new = [sample for sample in samples if sample.public_id not in known]
    applicants = people.pending_many(session, (sample.email for sample in new), actor)
    added = 0
    for sample in new:
        state = _STATES[sample.state]
        when = sample_day(sample.submitted)
        session.add(
            Application(
                public_id=sample.public_id,
                exercise_id=exercise.id,
                person_id=applicants[people.email_key(sample.email) or ""].id,
                name=sample.applicant,
                title=sample.title,
                state=state,
                started_at=when,
                submitted_at=None if state == "draft" else when,
                withdrawn_at=when if state == "withdrawn" else None,
                form_revision=None if state == "draft" else exercise.form_revision,
            )
        )
        added += 1
    if added:
        session.flush()
        audit.write_event(
            session,
            event_type="application.seeded",
            actor=actor,
            exercise=exercise,
            payload=audit.counts(added=added),
        )
    return added
