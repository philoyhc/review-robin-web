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


def test_a_csv_through_the_route_is_listed_and_audited() -> None:
    client = _client()
    sent = _post(client, {"action": "csv", "text": "Email,Name\ndee.csv@example.edu,Dee\n"})
    assert sent.status_code == 200, sent.text
    listed = [c for c in sent.json()["candidates"] if c["email"] == "dee.csv@example.edu"]
    assert len(listed) == 1 and listed[0]["name"] == "Dee"
    session = db.new_session()
    try:
        row = session.scalar(select(Invitee).where(Invitee.id == listed[0]["id"]))
        assert row is not None and row.via == "csv"
        audited = session.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.event_type == "invitee.added")
        )
        assert audited and audited >= 1
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


def test_an_empty_invite_list_is_warned_of_on_process() -> None:
    from applydesk.tests.test_new_exercise import _create, _post_process, _stage
    from applydesk.timeline_checks import NO_INVITEES

    client = _client()
    made = _create(client)
    form = {"from": "", "to": "", "receipt": False, "reminder": False}
    sent = {"stages": [_stage("Applications", form=form)], "who_may_apply": "invitation"}
    assert _post_process(client, made, sent).status_code == 200
    assert NO_INVITEES in client.get(f"{LOBBY}/{made}/process").text
    session = db.new_session()
    try:
        ada = people.pending(session, "ada.invitee@example.edu", None)
        session.commit()
        ada_id = ada.id
    finally:
        session.close()
    added = client.post(f"{LOBBY}/{made}/invitees", json={"action": "add", "person_id": ada_id})
    assert added.status_code == 200, added.text
    assert NO_INVITEES not in client.get(f"{LOBBY}/{made}/process").text


def test_the_invitees_tab_shows_while_the_form_is_for_invitees() -> None:
    """Segment AD2N: the tab sits after Process, only while Who may apply is
    Invitees as saved and no Create dossiers is on the timeline; its page
    answers either way."""
    from applydesk.tests.test_new_exercise import _create, _post_process, _stage

    client = _client()
    made = _create(client)
    tab = f'class="xnav-tab" href="/applydesk/operator/exercises/{made}/invitees"'
    form = {"from": "", "to": "", "receipt": False, "reminder": False}
    sent = {"stages": [_stage("Applications", form=form)], "who_may_apply": "open"}
    assert _post_process(client, made, sent).status_code == 200
    assert tab not in client.get(f"{LOBBY}/{made}/process").text
    assert client.get(f"{LOBBY}/{made}/invitees").status_code == 200
    assert _post_process(client, made, {**sent, "who_may_apply": "invitation"}).status_code == 200
    page = client.get(f"{LOBBY}/{made}/process").text
    assert tab in page
    process = page.index(f'href="/applydesk/operator/exercises/{made}/process"')
    form_tab = page.index(f'href="/applydesk/operator/exercises/{made}/form"')
    assert process < page.index(tab) < form_tab
    led = {"stages": [_stage("People", candidates=True), _stage("Applications", form=form)]}
    assert _post_process(client, made, led).status_code == 200
    assert tab not in client.get(f"{LOBBY}/{made}/process").text


def test_process_shows_count_lines_and_links_not_tables() -> None:
    """Segment AD2N: Process's Form and Create dossiers items keep their
    add rows and show a count line and a link, which says to save first
    while the page it names does not yet show the list."""
    from applydesk.tests.test_new_exercise import _create, _post_process, _stage

    client = _client()
    made = _create(client)
    base = f"/applydesk/operator/exercises/{made}"
    form = {"from": "", "to": "", "receipt": False, "reminder": False}
    sent = {"stages": [_stage("Applications", form=form)], "who_may_apply": "open"}
    assert _post_process(client, made, sent).status_code == 200
    page = client.get(f"{base}/process").text
    cards = page[page.index('id="pc-cards"') : page.index('<template id="pc-new-stage">')]
    assert f'<a href="{base}/invitees">Save, then manage on Invitees →</a>' in cards
    assert _post_process(client, made, {**sent, "who_may_apply": "invitation"}).status_code == 200
    page = client.get(f"{base}/process").text
    cards = page[page.index('id="pc-cards"') : page.index('<template id="pc-new-stage">')]
    assert f'<a href="{base}/invitees">Manage on Invitees →</a>' in cards
    assert "data-cand-list" not in cards and "data-cand-sum" in cards
    led = {"stages": [_stage("People", candidates=True), _stage("Applications", form=form)]}
    assert _post_process(client, made, led).status_code == 200
    page = client.get(f"{base}/process").text
    cards = page[page.index('id="pc-cards"') : page.index('<template id="pc-new-stage">')]
    assert f'<a href="{base}/dossiers">Manage on Dossiers →</a>' in cards
    assert "data-cand-list" not in cards
    fresh = page[page.index('<template id="pc-new-candidates">') :]
    assert "Save, then manage on Dossiers →" in fresh[: fresh.index("</template>")]


def test_the_invitees_page_says_when_create_dossiers_leaves_it_unused() -> None:
    """Cold read (AD2N): with Create dossiers on the timeline the list is
    unused even while Who may apply is stored as Invitees; and the Dossiers
    page's placeholder line says the card below keeps its changes."""
    from applydesk.tests.test_new_exercise import _create, _post_process, _stage

    client = _client()
    made = _create(client)
    base = f"/applydesk/operator/exercises/{made}"
    form = {"from": "", "to": "", "receipt": False, "reminder": False}
    sent = {"stages": [_stage("Applications", form=form)], "who_may_apply": "invitation"}
    assert _post_process(client, made, sent).status_code == 200
    assert "data-iv-unused" not in client.get(f"{base}/invitees").text
    led = {"stages": [_stage("People", candidates=True), _stage("Applications", form=form)]}
    assert _post_process(client, made, {**led, "who_may_apply": "invitation"}).status_code == 200
    assert "data-iv-unused" in client.get(f"{base}/invitees").text
    dossiers = client.get(f"{base}/dossiers").text
    assert "<em>Created by hand</em> keeps each change" in dossiers
