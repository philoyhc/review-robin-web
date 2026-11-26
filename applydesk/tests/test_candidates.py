"""The Candidates list, shown as Populate Dossiers (rulings 77, 83;
segments AD2C rung 9, AD2K; `applydesk/candidates.py`): entries added
through the search or a CSV, one dossier each, up to the most a person may
hold; each change audited; the item placed on one stage by Process's
Save."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from applydesk import candidates, db, people, stages
from applydesk.models import AuditEvent, Candidate, Exercise, Person
from applydesk.tests._host import host_with

MODEL = "wa9juxbc2t"
LOBBY = "/applydesk/operator/exercises"


def _client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0], follow_redirects=False)


def _post(client: TestClient, body: dict[str, Any]) -> Any:
    return client.post(f"{LOBBY}/{MODEL}/candidates", json=body)


def test_an_entry_a_dossier_up_to_the_most_per_person_and_no_revival() -> None:
    """Segment AD2K (ruling 83): each add is an entry; past the exercise's
    ``dossiers_per_person`` it is refused; removing an entry and adding the
    person again makes a new one, not the old one back."""
    session = db.new_session()
    try:
        ann = people.pending(session, "ann@example.edu", None)
        assert candidates.add(session, MODEL, ann, "search", None)
        assert not candidates.add(session, MODEL, ann, "search", None)  # one per person
        assert candidates.already(session, MODEL) == "Already listed."
        assert [c.email for c in candidates.listing(session, MODEL)] == ["ann@example.edu"]
        assert candidates.full(session, MODEL) == frozenset({ann.id})
        first = candidates.listing(session, MODEL)[0].id
        assert candidates.remove(session, MODEL, first, None)
        assert not candidates.remove(session, MODEL, first, None)
        assert candidates.listing(session, MODEL) == ()
        assert candidates.add(session, MODEL, ann, "csv", None)
        assert session.scalar(select(func.count()).select_from(Candidate)) == 2  # a new entry
        assert candidates.listing(session, MODEL)[0].id != first
        exercise = session.scalar(select(Exercise).where(Exercise.public_id == MODEL))
        assert exercise is not None
        exercise.dossiers_per_person = 2
        assert candidates.add(session, MODEL, ann, "search", None, title="Second project")
        assert [c.title for c in candidates.listing(session, MODEL)] == ["", "Second project"]
        assert not candidates.add(session, MODEL, ann, "search", None)
        assert candidates.already(session, MODEL) == "Already listed 2 times, the most allowed."
        events = list(session.scalars(select(AuditEvent.event_type).order_by(AuditEvent.id)))
        assert events.count("candidate.added") == 3 and events.count("candidate.removed") == 1
        session.commit()
    finally:
        session.close()


def test_a_csv_row_a_dossier_with_its_title_up_to_the_most() -> None:
    session = db.new_session()
    try:
        exercise = session.scalar(select(Exercise).where(Exercise.public_id == MODEL))
        assert exercise is not None
        exercise.dossiers_per_person = 2
        text = (
            "Email,Title\n"
            "eve@example.edu,Project A\n"
            "eve@example.edu,Project B\n"
            "eve@example.edu,Project C\n"
        )
        done = candidates.import_csv(session, MODEL, text, None)
        assert (done.added, done.already) == (2, 0)
        assert done.bad == ("Row 4: eve@example.edu is in the file more than 2 times.",)
        assert [c.title for c in candidates.listing(session, MODEL)] == ["Project A", "Project B"]
        session.commit()
    finally:
        session.close()


def test_a_csv_saves_its_good_rows_and_lists_the_rest_back() -> None:
    session = db.new_session()
    try:
        bob = people.pending(session, "bob@example.edu", None)
        candidates.add(session, MODEL, bob, "search", None)
        text = (
            "﻿Name,EMAIL\n"
            "Ada Lovelace,ada@example.edu\n"
            ",bob@example.edu\n"
            "Not one,nobody\n"
            "Ada again,ADA@example.edu\n"
            "\n"
        )
        done = candidates.import_csv(session, MODEL, text, None)
        assert (done.added, done.already) == (1, 1)
        assert done.bad == (
            "Row 4: “nobody” is not an email address.",
            "Row 5: ADA@example.edu is in the file twice.",
        )
        ada = session.scalar(select(Person).where(Person.email_key == "ada@example.edu"))
        assert ada is not None and ada.display_name == "Ada Lovelace"
        session.commit()
    finally:
        session.close()


def test_a_csv_address_too_long_to_store_is_a_bad_row() -> None:
    """Codex on #4161: an address longer than a person row holds is listed
    back with the bad rows, and the good rows still save."""
    long = "a" * 315 + "@x.edu"  # 321 characters: matches the pattern, too long
    session = db.new_session()
    try:
        done = candidates.import_csv(session, MODEL, f"Email\n{long}\nok@example.edu\n", None)
        assert done.added == 1 and len(done.bad) == 1
        assert done.bad[0].startswith("Row 2: “aaa") and "is not an email address" in done.bad[0]
        assert [c.email for c in candidates.listing(session, MODEL)] == ["ok@example.edu"]
    finally:
        session.close()


def test_a_csv_field_past_the_parser_s_limit_stops_the_read_not_the_upload() -> None:
    """Codex on #4161: a field longer than ``csv``'s limit raises
    ``csv.Error``; the rows before it save and the rest are listed back."""
    huge = "x" * 140_000
    session = db.new_session()
    try:
        text = f"Email,Name\nok@example.edu,Ok\nlate@example.edu,{huge}\nafter@example.edu,\n"
        done = candidates.import_csv(session, MODEL, text, None)
        assert done.added == 1
        assert done.bad == ("Row 3 could not be read; the rows after it were not read.",)
    finally:
        session.close()


def test_a_csv_without_an_email_column_is_refused() -> None:
    session = db.new_session()
    try:
        try:
            candidates.import_csv(session, MODEL, "Name\nAda\n", None)
        except candidates.Refused as why:
            assert "Email column" in str(why)
        else:
            raise AssertionError("refused")
    finally:
        session.close()


def test_the_routes_add_remove_and_upload() -> None:
    client = _client()
    session = db.new_session()
    try:
        cy = people.pending(session, "cy@example.edu", None)
        session.commit()
        cy_id = cy.id
    finally:
        session.close()
    found = client.get(f"{LOBBY}/{MODEL}/candidates/search", params={"q": "cy@ex"}).json()
    assert [p["id"] for p in found["on_record"]] == [cy_id]
    added = _post(client, {"action": "add", "person_id": cy_id})
    assert added.status_code == 200 and added.json()["said"] == "Added."
    assert [c["email"] for c in added.json()["candidates"]] == ["cy@example.edu"]
    # Listed as often as allowed: the search leaves them out, an add says so.
    again = client.get(f"{LOBBY}/{MODEL}/candidates/search", params={"q": "cy@ex"}).json()
    assert again["on_record"] == []
    assert _post(client, {"action": "add", "person_id": cy_id}).json()["said"] == "Already listed."
    upload = _post(client, {"action": "csv", "text": "Email\ndee@example.edu\nbad\n"})
    assert upload.status_code == 200
    assert upload.json()["said"] == "1 added." and len(upload.json()["bad"]) == 1
    entry = added.json()["candidates"][0]
    assert entry["person_id"] == cy_id and entry["title"] == ""
    removed = _post(client, {"action": "remove", "entry_id": entry["id"]})
    assert [c["email"] for c in removed.json()["candidates"]] == ["dee@example.edu"]
    for bad in ({"action": "add"}, {"action": "nothing"}, {"action": "csv", "text": 3}):
        refused = _post(client, bad)
        assert refused.status_code == 400 and "malformed" in refused.json()["error"]


def test_process_places_candidates_on_one_stage() -> None:
    """The item's place is saved with Process; two stages holding it is
    ruling 77 broken, refused."""
    from applydesk.tests.test_new_exercise import _post_process, _stage

    client = _client()
    form = {"from": "", "to": "", "receipt": False, "reminder": False}
    sent = {"stages": [_stage("Applications", form=form, candidates=True), _stage("Review")]}
    saved = _post_process(client, MODEL, sent)
    assert saved.status_code == 200, saved.text
    assert [st.candidates for st in stages.plan_of(MODEL).stages] == [True, False]
    page = client.get(f"{LOBBY}/{MODEL}/process").text
    assert (
        page.count('class="pc-item" data-item="candidates"') == 2
    )  # the stage's, and the template
    assert 'data-pc-act="candidates" disabled title="Another stage holds Populate Dossiers"' in page
    both = {
        "stages": [
            _stage("Applications", form=form, candidates=True),
            _stage("Review", candidates=True),
        ]
    }
    refused = _post_process(client, MODEL, both)
    assert (
        refused.status_code == 400
        and "More than one stage holds Populate Dossiers" in refused.json()["error"]
    )


def test_dossiers_per_person_is_saved_with_process_and_refused_below_what_is_held() -> None:
    """Segment AD2K: set on the first stage's populating item, saved with
    Process, audited; lowering it below what someone holds names them."""
    from applydesk.tests.test_new_exercise import _post_process, _stage

    client = _client()
    page = client.get(f"{LOBBY}/{MODEL}/process").text
    assert 'data-rel="per-person" value="1"' in page
    sent = {"stages": [_stage("People", candidates=True)], "per_person": 2}
    saved = _post_process(client, MODEL, sent)
    assert saved.status_code == 200, saved.text
    session = db.new_session()
    try:
        assert candidates.per_person(session, MODEL) == 2
        ann = people.pending(session, "ann@example.edu", None)
        ann.display_name = "Ann Lee"
        assert candidates.add(session, MODEL, ann, "search", None)
        assert candidates.add(session, MODEL, ann, "search", None)
        session.commit()
        kinds = list(session.scalars(select(AuditEvent.event_type)))
        assert "exercise.dossiers_per_person_set" in kinds
    finally:
        session.close()
    assert 'data-rel="per-person" value="2"' in client.get(f"{LOBBY}/{MODEL}/process").text
    lowered = _post_process(client, MODEL, {**sent, "per_person": 1})
    assert lowered.status_code == 400
    assert lowered.json()["error"] == (
        "Not saved: Ann Lee holds more than 1 dossier; remove entries first."
    )
    for bad in (0, 21):
        refused = _post_process(client, MODEL, {**sent, "per_person": bad})
        assert refused.status_code == 400 and "1 to 20" in refused.json()["error"]
    # Left out, it is unchanged.
    assert _post_process(client, MODEL, {"stages": sent["stages"]}).status_code == 200
