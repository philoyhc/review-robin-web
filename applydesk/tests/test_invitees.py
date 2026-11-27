"""A Form's invitees (ruling 84, segment AD2I, `applydesk/invitees.py`):
people who may submit when the Form's Who may apply is Invitees, added by
the search or a CSV, once each, removed and invited again on the same row;
each change audited; the list on the Form while Invitees is chosen."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import func, select

from applydesk import db, invitees, people
from applydesk.models import AuditEvent, Invitee
from applydesk.tests._host import host_with

MODEL = "wa9juxbc2t"
LOBBY = "/applydesk/operator/exercises"


def _client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0], follow_redirects=False)


def _post(client: TestClient, body: dict[str, Any]) -> Any:
    return client.post(f"{LOBBY}/{MODEL}/invitees", json=body)


def test_someone_is_invited_once_and_again_on_the_same_row() -> None:
    session = db.new_session()
    try:
        ann = people.pending(session, "ann@example.edu", None)
        assert invitees.add(session, MODEL, ann, "search", None)
        assert not invitees.add(session, MODEL, ann, "search", None)  # invited already
        assert invitees.already(session, MODEL) == "Already invited."
        assert invitees.full(session, MODEL) == frozenset({ann.id})
        row = invitees.listing(session, MODEL)[0]
        assert invitees.remove(session, MODEL, row.id, None)
        assert invitees.listing(session, MODEL) == ()
        assert invitees.add(session, MODEL, ann, "csv", None)
        assert session.scalar(select(func.count()).select_from(Invitee)) == 1  # the same row
        kinds = list(session.scalars(select(AuditEvent.event_type)))
        assert kinds.count("invitee.added") == 2 and kinds.count("invitee.removed") == 1
        session.commit()
    finally:
        session.close()


def test_a_csv_invites_its_good_rows() -> None:
    session = db.new_session()
    try:
        text = "Email,Name\nbea@example.edu,Bea\nbea@example.edu,Bea\nnobody\n"
        done = invitees.import_csv(session, MODEL, text, None)
        assert (done.added, done.already) == (1, 0)
        assert done.bad == (
            "Row 3: bea@example.edu is in the file twice.",
            "Row 4: “nobody” is not an email address.",
        )
        session.commit()
    finally:
        session.close()


def test_the_routes_invite_and_take_off() -> None:
    client = _client()
    session = db.new_session()
    try:
        cy = people.pending(session, "cy.invitee@example.edu", None)
        session.commit()
        cy_id = cy.id
    finally:
        session.close()
    found = client.get(f"{LOBBY}/{MODEL}/invitees/search", params={"q": "cy.invitee"}).json()
    assert [p["id"] for p in found["on_record"]] == [cy_id]
    added = _post(client, {"action": "add", "person_id": cy_id})
    assert added.status_code == 200 and added.json()["said"] == "Added."
    again = client.get(f"{LOBBY}/{MODEL}/invitees/search", params={"q": "cy.invitee"}).json()
    assert again["on_record"] == []  # invited: left out
    entry = added.json()["candidates"][0]
    removed = _post(client, {"action": "remove", "entry_id": entry["id"]})
    assert removed.json()["candidates"] == []


def test_the_form_shows_the_list_while_invitees_is_chosen() -> None:
    from applydesk.tests.test_new_exercise import _create, _post_process, _stage

    client = _client()
    made = _create(client)
    form = {"from": "", "to": "", "receipt": False, "reminder": False}
    sent = {"stages": [_stage("Applications", form=form)], "who_may_apply": "open"}
    assert _post_process(client, made, sent).status_code == 200
    page = client.get(f"{LOBBY}/{made}/process").text
    cards = page[page.index('id="pc-cards"') : page.index('<template id="pc-new-stage">')]
    assert "data-invitees-row hidden" in cards and 'data-cand-kind="invitees"' in cards
    assert _post_process(client, made, {**sent, "who_may_apply": "invitation"}).status_code == 200
    page = client.get(f"{LOBBY}/{made}/process").text
    cards = page[page.index('id="pc-cards"') : page.index('<template id="pc-new-stage">')]
    assert "data-invitees-row hidden" not in cards
