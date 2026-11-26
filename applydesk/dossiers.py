"""An exercise's dossiers (segment AD2F; rulings 25, 26, 32, 81; AD-44),
kept in the `dossier` table: each its own public ID and its source, an
application or a Candidates row.

Until AD4 mints a form's dossiers at submit or at its close, the only
application dossiers are the samples', which the localhost seed records
with the IDs they carry (ruling 74). A Candidates item mints a dossier per
candidate where the timeline holds no form, once the exercise is
published and on each later add (ruling 81, `sync_candidates`)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from applydesk import audit, db, ids, sample_data
from applydesk.models import Application, Candidate, Dossier, Exercise, Person
from applydesk.models import Stage as StageRow

#: Tries for a fresh public ID before giving up (ruling 53: unique by index).
_ATTEMPTS = 8


def record_samples(session: Session, exercise: Exercise, actor: Person | None) -> int:
    """Record the dossier of each of `exercise`'s stored sample applications
    that is not a draft (ruling 32: a draft has none), by the ID the sample
    carries; one already on record is left alone. Returns how many were
    added, audited as one event when any were."""
    rows = session.execute(
        select(Application.id, Application.public_id)
        .outerjoin(Dossier, Dossier.application_id == Application.id)
        .where(
            Application.exercise_id == exercise.id,
            Application.state != "draft",
            Dossier.id.is_(None),
        )
        .order_by(Application.id)
    ).all()
    carried = {
        a.public_id: a.dossier_id for a in sample_data.sample_applications(exercise.public_id)
    }
    added = 0
    for application_id, public_id in rows:
        dossier_id = carried.get(public_id, "")
        if not dossier_id:
            continue
        session.add(
            Dossier(public_id=dossier_id, exercise_id=exercise.id, application_id=application_id)
        )
        added += 1
    if added:
        session.flush()
        audit.write_event(
            session,
            event_type="dossier.seeded",
            actor=actor,
            exercise=exercise,
            payload=audit.counts(added=added),
        )
    return added


def feeds_gates(session: Session, exercise: Exercise) -> bool:
    """Whether the exercise's Candidates feed gates (ruling 81, author
    2026-11-26): its stored timeline holds no form. A timeline never saved
    holds the form a new exercise starts with, so it is a roster."""
    if exercise.process_revision < 1:  # never saved: the starting stage holds the form
        return False
    live = select(StageRow).where(
        StageRow.exercise_id == exercise.id, StageRow.retired_at.is_(None)
    )
    if session.scalar(select(exists(live))) is not True:
        return False
    return session.scalar(select(exists(live.where(StageRow.holds_form.is_(True))))) is not True


def published(session: Session, exercise: Exercise) -> bool:
    """Whether any of the exercise's live stages is published (ruling 35)."""
    return (
        session.scalar(
            select(
                exists().where(
                    StageRow.exercise_id == exercise.id,
                    StageRow.retired_at.is_(None),
                    StageRow.status == "published",
                )
            )
        )
        is True
    )


def _fresh_id(session: Session) -> str:
    """A public ID no exercise, application or dossier holds (ruling 53)."""
    for _ in range(_ATTEMPTS):
        found = ids.generate_public_id()
        taken = session.scalar(
            select(
                exists().where(Dossier.public_id == found)
                | exists().where(Application.public_id == found)
                | exists().where(Exercise.public_id == found)
            )
        )
        if taken is not True:
            return found
    raise RuntimeError("could not mint a dossier ID")


def sync_candidates(session: Session, exercise: Exercise, actor: Person | None) -> int:
    """Give each current candidate a dossier where the exercise's Candidates
    feed gates and it is published (ruling 81): minted once, a re-added
    candidate's retired one revived. Returns how many were minted or
    revived, audited as one event when any were. Flushes."""
    if not (feeds_gates(session, exercise) and published(session, exercise)):
        return 0
    listed = session.scalars(
        select(Candidate)
        .where(Candidate.exercise_id == exercise.id, Candidate.removed_at.is_(None))
        .order_by(Candidate.added_at, Candidate.id)
    ).all()
    held = {
        d.candidate_id: d
        for d in session.scalars(
            select(Dossier).where(
                Dossier.exercise_id == exercise.id, Dossier.candidate_id.is_not(None)
            )
        )
    }
    made = revived = 0
    for candidate in listed:
        dossier = held.get(candidate.id)
        if dossier is None:
            session.add(
                Dossier(
                    public_id=_fresh_id(session),
                    exercise_id=exercise.id,
                    candidate_id=candidate.id,
                )
            )
            session.flush()
            made += 1
        elif dossier.retired_at is not None:
            dossier.retired_at = None
            revived += 1
    if made or revived:
        session.flush()
        audit.write_event(
            session,
            event_type="dossier.minted",
            actor=actor,
            exercise=exercise,
            payload=audit.counts(minted=made, revived=revived),
        )
    return made + revived


def retire_for(
    session: Session, exercise: Exercise, candidate: Candidate, actor: Person | None
) -> bool:
    """Retire a removed candidate's dossier, if they have a live one (until
    AD2H records entries, nothing holds one). Flushes."""
    dossier = session.scalar(
        select(Dossier).where(Dossier.candidate_id == candidate.id, Dossier.retired_at.is_(None))
    )
    if dossier is None:
        return False
    dossier.retired_at = datetime.now(UTC)
    session.flush()
    audit.write_event(
        session,
        event_type="dossier.retired",
        actor=actor,
        exercise=exercise,
        refs={"dossier_id": dossier.id},
    )
    return True


def candidate_rows(exercise_id: str) -> tuple[tuple[str, str, str], ...]:
    """The exercise's live candidate dossiers as (Dossier ID, name, email),
    in the order their candidates were added, read in a session of their
    own (`stages.plan_of`, which no route hands a session). The name is the
    person's, else their address."""
    session = db.new_session()
    try:
        rows = session.execute(
            select(Dossier.public_id, Person.display_name, Person.email)
            .join(Candidate, Candidate.id == Dossier.candidate_id)
            .join(Person, Person.id == Candidate.person_id)
            .join(Exercise, Exercise.id == Dossier.exercise_id)
            .where(Exercise.public_id == exercise_id, Dossier.retired_at.is_(None))
            .order_by(Candidate.added_at, Candidate.id)
        ).all()
    finally:
        session.close()
    return tuple((d, name or email or "", email or "") for d, name, email in rows)
