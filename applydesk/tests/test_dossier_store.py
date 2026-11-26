"""Dossiers in the database (segment AD2F rung 2; AD-44): the seed records
each sample application's dossier, but a draft's, by the ID it carries;
the table holds exactly one source, each at most once."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from applydesk import db, sample_data
from applydesk.models import Application, AuditEvent, Dossier
from applydesk.seed import seed

pytestmark = pytest.mark.usefixtures("applydesk_db")


def test_the_seed_records_each_non_draft_sample_dossier_once() -> None:
    session = db.new_session()
    rows = session.execute(
        select(Dossier.public_id, Application.public_id, Application.state).join(
            Application, Application.id == Dossier.application_id
        )
    ).all()
    not_drafts = [a for a in sample_data.APPLICATIONS if a.state != "Draft"]
    assert len(rows) == len(not_drafts) == 104
    assert {(d, a) for d, a, _ in rows} == {(a.dossier_id, a.public_id) for a in not_drafts}
    assert all(state != "draft" for _, _, state in rows)
    assert seed(session).dossiers_added == 0  # a second run adds none
    assert session.scalar(select(func.count()).select_from(Dossier)) == 104
    seeded = session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "dossier.seeded")
    ).all()
    assert sum(e.detail["counts"]["added"] for e in seeded) == 104
    session.close()


def test_a_dossier_has_exactly_one_source() -> None:
    session = db.new_session()
    taken = session.scalars(select(Dossier)).first()
    assert taken is not None
    session.add(Dossier(public_id="zz2zz2zz2z", exercise_id=taken.exercise_id))
    with pytest.raises(IntegrityError):  # neither source
        session.flush()
    session.rollback()
    session.add(
        Dossier(
            public_id="zz2zz2zz2y",
            exercise_id=taken.exercise_id,
            application_id=taken.application_id,
        )
    )
    with pytest.raises(IntegrityError):  # an application's second dossier
        session.flush()
    session.close()


def test_the_pages_read_a_dossier_id_from_the_table() -> None:
    """Rung 3: an application's dossier ID is the stored one; a draft has
    none, whatever the sample code carries."""
    model = "wa9juxbc2t"
    first = sample_data.applications_of(model)[0]
    session = db.new_session()
    row = session.scalars(select(Dossier).where(Dossier.public_id == first.dossier_id)).one()
    row.public_id = "zz2zz2zz2z"
    session.commit()
    session.close()
    assert sample_data.applications_of(model)[0].dossier_id == "zz2zz2zz2z"
    assert sample_data.by_dossier(model, "zz2zz2zz2z") is not None
    assert sample_data.by_dossier(model, first.dossier_id) is None
    drafts = [a for a in sample_data.applications_of(model) if a.state == "Draft"]
    assert drafts and all(a.dossier_id == "" for a in drafts)
