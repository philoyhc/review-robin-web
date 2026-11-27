"""An exercise's dossiers (segment AD2F; rulings 25, 26, 32, 81; AD-44),
kept in the `dossier` table: each its own public ID and its source, an
application or a Candidates row.

Until AD4 mints a form's dossiers at submit or at its close, the only
application dossiers are the samples', which the localhost seed records
with the IDs they carry (ruling 74). *Create dossiers* (the Candidates
item) mints a dossier per entry where it is the first item, once the
exercise is published and on each later add (rulings 81, 83,
`sync_candidates`)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import exists, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from applydesk import audit, db, ids, sample_data
from applydesk.models import Application, Candidate, Dossier, Exercise, Person
from applydesk.models import Stage as StageRow

#: Tries for a fresh public ID before giving up (AD-53: unique by index).
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
    """Whether the exercise's Candidates (*Create dossiers*) create its
    dossiers (ruling 83 as amended, author 2026-11-27): its stored
    timeline's first stage holds the item. A Form may follow it, on that
    stage or a later one, and writes to the dossiers it made; a Form first
    creates them itself, so the item is not offered after one. A timeline
    never saved has a blank first stage, so nothing is created yet."""
    if exercise.process_revision < 1:
        return False
    first = session.scalars(
        select(StageRow)
        .where(StageRow.exercise_id == exercise.id, StageRow.retired_at.is_(None))
        .order_by(StageRow.position, StageRow.id)
        .limit(1)
    ).first()
    return first is not None and first.holds_candidates


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
    """A public ID no exercise, application or dossier holds (AD-53)."""
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
    """Give each current entry a dossier where Create dossiers is the
    exercise's first item and it is published (rulings 81, 83): minted
    once, one per entry. A removed entry's dossier stays retired; adding the
    person again is a new entry with a dossier of its own (segment AD2K).
    Returns how many were minted, audited as one event when any were.
    Flushes."""
    if not (feeds_gates(session, exercise) and published(session, exercise)):
        return 0
    held = select(Dossier.candidate_id).where(Dossier.candidate_id.is_not(None))
    listed = session.scalars(
        select(Candidate)
        .where(
            Candidate.exercise_id == exercise.id,
            Candidate.removed_at.is_(None),
            Candidate.id.not_in(held),
        )
        .order_by(Candidate.added_at, Candidate.id)
    ).all()
    made = 0
    for candidate in listed:
        try:
            with session.begin_nested():  # another request may mint it meanwhile
                session.add(
                    Dossier(
                        public_id=_fresh_id(session),
                        exercise_id=exercise.id,
                        candidate_id=candidate.id,
                    )
                )
        except IntegrityError:
            continue
        made += 1
    if made:
        session.flush()
        audit.write_event(
            session,
            event_type="dossier.minted",
            actor=actor,
            exercise=exercise,
            payload=audit.counts(minted=made),
        )
    return made


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


@dataclass(frozen=True)
class HandRow:
    """One Create dossiers entry as the Dossiers page's one table draws it
    (author, 2026-11-27): ``dossier_id`` its live dossier's ID, "" until
    one is minted (before publishing)."""

    entry_id: int
    dossier_id: str
    name: str
    email: str
    title: str


def hand_rows(exercise_id: str) -> tuple[HandRow, ...]:
    """The exercise's live Create dossiers entries with their dossiers, if
    minted, in the order they were added, read in a session of their own."""
    session = db.new_session()
    try:
        rows = session.execute(
            select(
                Candidate.id, Dossier.public_id, Person.display_name, Person.email, Candidate.title
            )
            .join(Person, Person.id == Candidate.person_id)
            .join(Exercise, Exercise.id == Candidate.exercise_id)
            .outerjoin(
                Dossier,
                (Dossier.candidate_id == Candidate.id) & Dossier.retired_at.is_(None),
            )
            .where(Exercise.public_id == exercise_id, Candidate.removed_at.is_(None))
            .order_by(Candidate.added_at, Candidate.id)
        ).all()
    finally:
        session.close()
    return tuple(
        HandRow(entry, dossier or "", name or email or "", email or "", title or "")
        for entry, dossier, name, email, title in rows
    )
