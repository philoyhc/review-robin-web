"""An exercise's own settings, stored (segment AD2B): the seed records
each sample's settings once, NULL for unset, and the pages read them laid
over the sample's (rung 2); Details' *Lock* saves them, refused if stale
(rung 3)."""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from applydesk import db, exercises, sample_data, seed
from applydesk.models import AuditEvent, Exercise
from applydesk.tests._host import host_with

EX = "wa9juxbc2t"  # RA-2027
BLANK = "n5wg8tjr3e"  # Graduate Travel Grant: "Not set" everywhere


def _seed_settings() -> None:
    session = db.new_session()
    seed.seed(session)  # the conftest's seed already did: changes nothing
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
    """A row at revision 0 has nothing recorded: the sample's stand."""
    session = db.new_session()
    ra = session.scalar(select(Exercise).where(Exercise.public_id == EX))
    assert ra is not None
    ra.revision, ra.name = 0, "Ignored"
    session.commit()
    session.close()
    sample = sample_data.exercise(EX)
    assert sample is not None and exercises.stored(sample) == sample


# --- Rung 3: Details saves to the database ---
DETAILS = f"/applydesk/operator/exercises/{EX}/details"


def _client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0])


def _good(**changes: Any) -> dict[str, Any]:
    """Details as the card sends RA-2027's, at the seed's revision."""
    return {
        "revision": 1,
        "name": "Recruitment and Selection of Residential Assistants",
        "code": "RA-2027",
        "description": "Look after a house of residents.",
        "contact": "",
        "timezone": sample_data.DEFAULT_TIMEZONE,
        "eligibility": "Open to all signed in",
        "blind": False,  # RA-2027's, fixed now a gate's stage is published
        **changes,
    }


def _row() -> Exercise:
    session = db.new_session()
    found = session.scalar(select(Exercise).where(Exercise.public_id == EX))
    session.close()
    assert found is not None
    return found


def test_lock_on_a_sample_saves_and_survives() -> None:
    client = _client()
    reply = client.post(DETAILS, json=_good())
    assert reply.status_code == 200 and reply.json() == {"saved": True, "revision": 2}
    row = _row()
    # The default timezone and an empty contact are NULL (AD-54).
    assert (row.description, row.blind, row.help_contact, row.timezone) == (
        "Look after a house of residents.",
        False,
        None,
        None,
    )
    assert "Look after a house of residents." in client.get(DETAILS[: -len("/details")]).text
    session = db.new_session()
    event = session.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "exercise.details_changed")
    ).one()
    session.close()
    # Only what changed is audited.
    assert set(event.detail["changes"]) == {"description", "help_contact"}


def test_a_stale_lock_is_refused_and_saves_nothing() -> None:
    client = _client()
    assert client.post(DETAILS, json=_good(name="First")).status_code == 200
    stale = client.post(DETAILS, json=_good(name="Second"))  # opened at 1, now 2
    assert stale.status_code == 409 and "someone else changed" in stale.json()["error"]
    assert (_row().name, _row().revision) == ("First", 2)


def test_an_unchanged_lock_keeps_the_revision() -> None:
    sample = sample_data.exercise(EX)
    assert sample is not None
    same = _good(
        description=sample.summary,
        contact=sample.help_contact,
        blind=sample.blind,
        timezone=sample.timezone or sample_data.DEFAULT_TIMEZONE,
    )
    assert _client().post(DETAILS, json=same).json() == {"saved": True, "revision": 1}


def test_not_set_is_stored_as_null() -> None:
    """AD-60: "Not set" eligibility is NULL, never the words."""
    client = _client()
    blank = f"/applydesk/operator/exercises/{BLANK}/details"
    sent = _good(code="", eligibility="Not set", name="Graduate Travel Grant 2027")
    assert client.post(blank, json=sent).status_code == 200
    session = db.new_session()
    row = session.scalar(select(Exercise).where(Exercise.public_id == BLANK))
    session.close()
    assert row is not None and (row.eligibility, row.code, row.code_key) == (None, None, None)


@pytest.mark.parametrize("code", ["ra-2027", "RA-2027"])
def test_another_live_exercise_s_code_is_refused(code: str) -> None:
    blank = f"/applydesk/operator/exercises/{BLANK}/details"
    reply = _client().post(blank, json=_good(code=code, name="Graduate Travel Grant 2027"))
    assert reply.status_code == 400 and reply.json()["field"] == "code"
    # The other exercise unnamed: the viewer may not operate it (AD2G cold read).
    assert "already another live exercise's code" in reply.json()["error"]
    assert "Recruitment" not in reply.json()["error"]


def test_an_archived_exercise_frees_its_code() -> None:
    session = db.new_session()
    ra = session.scalar(select(Exercise).where(Exercise.public_id == EX))
    assert ra is not None
    ra.archived_at = datetime.now(UTC)
    session.commit()
    session.close()
    blank = f"/applydesk/operator/exercises/{BLANK}/details"
    reply = _client().post(blank, json=_good(code="RA-2027", name="Graduate Travel Grant 2027"))
    assert reply.status_code == 200


def test_home_names_the_revision_of_the_settings_it_shows() -> None:
    """Codex on #4137: Home's values and the revision Lock names come
    from one read (`stored_at`); this checks they agree after a save."""
    sample = sample_data.exercise(EX)
    assert sample is not None
    assert _client().post(DETAILS, json=_good(name="Renamed")).status_code == 200
    shown, revision = exercises.stored_at(sample)
    assert (shown.name, revision) == ("Renamed", 2)
    page = _client().get(DETAILS[: -len("/details")]).text
    assert 'data-dt-revision="2"' in page and "Renamed" in page


@pytest.mark.parametrize(
    ("change", "field"),
    [
        ({"blind": True}, "blind"),
        ({"code": "RA-28"}, "code"),
    ],
)
def test_what_the_page_locks_the_server_refuses(change: dict[str, Any], field: str) -> None:
    """Cold read: RA-2027 is published with a gate's stage published, so
    its code and blind review are fixed on the server too, not only by the
    page's disabled inputs. (Who may apply is the Form's: ruling 84.)"""
    reply = _client().post(DETAILS, json=_good(**change))
    assert reply.status_code == 400 and reply.json()["field"] == field
    assert _row().revision == 1


def test_a_code_is_measured_as_its_key_is() -> None:
    """Cold read: "ß" casefolds to "ss", so 40 of them would not fit the key."""
    blank = f"/applydesk/operator/exercises/{BLANK}/details"
    reply = _client().post(blank, json=_good(code="ß" * 21, name="G"))
    assert reply.status_code == 400 and reply.json()["field"] == "code"


def test_who_may_apply_is_fixed_while_the_form_is_published() -> None:
    """Codex on #4259: a published Form keeps who may apply, as Details'
    control did; an unchanged value saves nothing and is not refused."""
    ra = sample_data.exercise("wa9juxbc2t")  # its Form's stage is published
    assert ra is not None
    session = db.new_session()
    try:
        row = session.scalar(select(Exercise).where(Exercise.public_id == ra.public_id))
        assert row is not None
        stored = row.eligibility or "open"
        other = "invitation" if stored == "open" else "open"
        assert not exercises.set_eligibility(session, ra, stored, None)
        row.eligibility = None  # unset reads as Anyone signed in
        assert not exercises.set_eligibility(session, ra, "open", None)
        row.eligibility = stored
        with pytest.raises(exercises.Refused, match="The Form is published"):
            exercises.set_eligibility(session, ra, other, None)
    finally:
        session.rollback()
        session.close()
