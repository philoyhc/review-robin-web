"""An exercise's dossiers (segment AD2F; rulings 25, 26, 32, 81; AD-44),
kept in the `dossier` table: each its own public ID and its source, an
application or a Candidates row.

Until AD4 mints a form's dossiers at submit or at its close, the only
application dossiers are the samples', which the localhost seed records
with the IDs they carry (ruling 74)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from applydesk import audit, sample_data
from applydesk.models import Application, Dossier, Exercise, Person


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
    added = 0
    for application_id, public_id in rows:
        dossier_id = sample_data.sample_dossier_id(public_id)
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
