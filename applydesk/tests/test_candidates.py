"""The Candidates list (ruling 77, segment AD2C rung 9,
`applydesk/candidates.py`): people added through the search or a CSV,
listed once, removed and added again on the same row, each change
audited; the item placed on one stage by Process's Save."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from applydesk import candidates, db, people, stages
from applydesk.models import AuditEvent, Candidate, Person
from applydesk.tests._host import host_with

MODEL = "wa9juxbc2t"
LOBBY = "/applydesk/operator/exercises"


def _client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0], follow_redirects=False)


def _post(client: TestClient, body: dict[str, Any]) -> Any:
    return client.post(f"{LOBBY}/{MODEL}/candidates", json=body)


def test_someone_is_listed_once_and_removed_then_added_again_on_the_same_row() -> None:
    session = db.new_session()
    try:
        ann = people.pending(session, "ann@example.edu", None)
        assert candidates.add(session, MODEL, ann, "search", None)
        assert not candidates.add(session, MODEL, ann, "search", None)  # listed already
        assert [c.email for c in candidates.listing(session, MODEL)] == ["ann@example.edu"]
        assert candidates.remove(session, MODEL, ann.id, None)
        assert candidates.listing(session, MODEL) == ()
        assert candidates.add(session, MODEL, ann, "csv", None)
        assert session.scalar(select(func.count()).select_from(Candidate)) == 1
        events = list(session.scalars(select(AuditEvent.event_type).order_by(AuditEvent.id)))
        assert events.count("candidate.added") == 2 and events.count("candidate.removed") == 1
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
    # Listed already: the search leaves them out.
    again = client.get(f"{LOBBY}/{MODEL}/candidates/search", params={"q": "cy@ex"}).json()
    assert again["on_record"] == []
    upload = _post(client, {"action": "csv", "text": "Email\ndee@example.edu\nbad\n"})
    assert upload.status_code == 200
    assert upload.json()["said"] == "1 added." and len(upload.json()["bad"]) == 1
    removed = _post(client, {"action": "remove", "person_id": cy_id})
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
