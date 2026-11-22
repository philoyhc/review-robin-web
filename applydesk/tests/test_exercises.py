"""An exercise's own settings, stored (segment AD2B rung 2): the seed
records each sample's settings once, NULL for unset, and the pages read
them laid over the sample's, unchanged in what they show."""

from __future__ import annotations

import dataclasses

from fastapi.testclient import TestClient
from sqlalchemy import select

from applydesk import db, exercises, sample_data, seed
from applydesk.models import AuditEvent, Exercise
from applydesk.tests._host import host_with

EX = "wa9juxbc2t"  # RA-2027
BLANK = "n5wg8tjr3e"  # Graduate Travel Grant: "Not set" everywhere


def _seed_settings() -> None:
    session = db.new_session()
    seed.seed(session)  # the conftest's seed recorded grants only
    session.close()


def test_the_seed_records_each_sample_s_settings_once_null_for_unset() -> None:
    _seed_settings()
    session = db.new_session()
    try:
        ra = session.scalar(select(Exercise).where(Exercise.public_id == EX))
        blank = session.scalar(select(Exercise).where(Exercise.public_id == BLANK))
        assert ra is not None and blank is not None
        assert (ra.name, ra.code, ra.code_key, ra.eligibility, ra.revision) == (
            "Recruitment and Selection of Residential Assistants",
            "RA-2027",
            "ra-2027",
            "open",
            1,
        )
        assert ra.help_contact == "ra-recruitment@example.edu" and ra.timezone is None
        # The blank draft: no code, no description, eligibility unset (AD-60).
        assert (blank.code, blank.description, blank.eligibility) == (None, None, None)
        assert exercises.tags_of(session, ra) == ("Residential", "2027")
        events = list(
            session.scalars(
                select(AuditEvent.event_type).where(
                    AuditEvent.event_type == "exercise.settings_recorded"
                )
            )
        )
        assert len(events) == len(sample_data.EXERCISES)
    finally:
        session.close()
    _seed_settings()  # a second run changes nothing
    session = db.new_session()
    ra = session.scalar(select(Exercise).where(Exercise.public_id == EX))
    assert ra is not None and ra.revision == 1
    assert len(exercises.tags_of(session, ra)) == 2
    session.close()


def test_the_pages_read_the_stored_settings_unchanged() -> None:
    """Overlaying the stored settings gives back the sample, field for
    field: rung 2 changes what is stored, not what any page shows."""
    _seed_settings()
    for sample in sample_data.EXERCISES:
        assert exercises.stored(sample) == sample, sample.public_id
    assert exercises.stored_all(sample_data.EXERCISES) == sample_data.EXERCISES


def test_a_stored_change_shows_on_the_pages() -> None:
    _seed_settings()
    session = db.new_session()
    ra = session.scalar(select(Exercise).where(Exercise.public_id == EX))
    assert ra is not None
    ra.name, ra.blind, ra.timezone, ra.eligibility = "RA 2027", True, "Asia/Tokyo", None
    session.commit()
    session.close()
    sample = sample_data.exercise(EX)
    assert sample is not None
    shown = exercises.stored(sample)
    assert (
        dataclasses.replace(
            sample,
            name="RA 2027",
            blind=True,
            timezone="Asia/Tokyo",
            eligibility="Not set",
            created="2026-08-04T10:12+09:00",  # the same moment, in Tokyo's time
        )
        == shown
    )
    home = TestClient(host_with(("applydesk",))[0]).get(f"/applydesk/operator/exercises/{EX}")
    assert "RA 2027" in home.text


def test_a_row_without_settings_keeps_the_sample_s() -> None:
    """The conftest's seed made rows with revision 0: nothing recorded."""
    sample = sample_data.exercise(EX)
    assert sample is not None and exercises.stored(sample) == sample
