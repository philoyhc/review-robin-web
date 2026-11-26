"""Applications in the database (segment AD2J; AD-38): the seed records
the samples', each applicant a pending person, each state with its times."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select

from applydesk import db, sample_data
from applydesk.applications import sample_day
from applydesk.models import Application, AuditEvent, Person
from applydesk.seed import seed

pytestmark = pytest.mark.usefixtures("applydesk_db")


def test_the_seed_records_every_sample_application_once() -> None:
    session = db.new_session()
    stored = session.scalar(select(func.count()).select_from(Application))
    assert stored == len(sample_data.APPLICATIONS) == 108
    assert seed(session).applications_added == 0  # a second run adds none
    assert session.scalar(select(func.count()).select_from(Application)) == stored
    seeded = list(
        session.scalars(select(AuditEvent).where(AuditEvent.event_type == "application.seeded"))
    )
    assert sum(e.detail["counts"]["added"] for e in seeded) == stored
    session.close()


def test_each_state_keeps_the_times_it_has() -> None:
    session = db.new_session()
    rows = {a.public_id: a for a in session.scalars(select(Application))}
    for sample in sample_data.APPLICATIONS:
        row = rows[sample.public_id]
        assert row.state == sample.state.lower()
        assert row.started_at is not None
        assert (row.submitted_at is None) == (row.state == "draft")
        assert (row.withdrawn_at is None) == (row.state != "withdrawn")
    session.close()


def test_an_applicant_is_a_pending_person_by_address() -> None:
    session = db.new_session()
    sample = sample_data.APPLICATIONS[0]
    row = session.scalars(
        select(Application).where(Application.public_id == sample.public_id)
    ).one()
    person = session.get(Person, row.person_id)
    assert person is not None and person.object_id is None
    assert person.email_key == sample.email.casefold()
    assert row.name == sample.applicant
    session.close()


def test_a_sample_day_keeps_its_date_east_and_west() -> None:
    when = sample_day("3 Sep 2026")
    assert when == datetime(2026, 9, 3, 12, tzinfo=UTC)


def test_pending_many_reuses_a_pending_person_and_makes_one_per_address() -> None:
    from applydesk import people

    session = db.new_session()
    kept = people.pending(session, "Lee@Example.edu", None)
    found = people.pending_many(
        session, ["lee@example.edu ", "New@Example.edu", "new@example.edu"], None
    )
    assert found["lee@example.edu"].id == kept.id
    assert set(found) == {"lee@example.edu", "new@example.edu"}
    made = session.scalars(select(Person).where(Person.email_key == "new@example.edu")).all()
    assert len(made) == 1 and made[0].email == "New@Example.edu"
    session.close()
