"""An exercise's applications (segment AD2J; AD-38), kept in the
`application` table: each one's applicant a person (ruling 73), its state
`draft`, `submitted` or `withdrawn`, and the time of each move.

Applicants submit from AD4. Until then the only applications are the
samples', which the localhost seed records (ruling 74)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from applydesk import audit, people, sample_data
from applydesk.models import Application, Exercise, Person

#: A sample's state, as `sample_data` words it, and the stored one.
_STATES = {"Draft": "draft", "Submitted": "submitted", "Withdrawn": "withdrawn"}


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
    added = 0
    for sample in samples:
        if sample.public_id in known:
            continue
        state = _STATES[sample.state]
        when = sample_day(sample.submitted)
        session.add(
            Application(
                public_id=sample.public_id,
                exercise_id=exercise.id,
                person_id=people.pending(session, sample.email, actor=actor).id,
                name=sample.applicant,
                title=sample.title,
                state=state,
                started_at=when,
                submitted_at=None if state == "draft" else when,
                withdrawn_at=when if state == "withdrawn" else None,
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
