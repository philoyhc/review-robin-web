"""*New exercise* (segment AD1N, made ordinary by AD2G Item 1): a blank
draft in the database with the viewer its Owner, at most
`exercises.MOST_MADE` live of their making; its Setup pages save into it
as every exercise's do."""

from __future__ import annotations

import re
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from applydesk import db, exercises, operators, people, sample_data
from applydesk.models import AuditEvent, Exercise
from applydesk.tests._host import host_with
from applydesk.web import MAX_BODY
from cordware.settings import identity_settings

LOBBY = "/applydesk/operator/exercises"


def _client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0], follow_redirects=False)


def _create(client: TestClient, name: str = "Summer Bursary 2027") -> str:
    reply = client.post(f"{LOBBY}/new", data={"name": name})
    assert reply.status_code == 303, reply.text
    found = re.fullmatch(r"/applydesk/operator/exercises/(\w+)", reply.headers["location"])
    assert found, reply.headers["location"]
    return found.group(1)


def test_new_exercise_makes_a_blank_draft_and_lands_on_its_home() -> None:
    client = _client()
    lobby = client.get(LOBBY).text
    assert (
        'data-nx-open aria-expanded="false"' in lobby
        and "disabled" not in lobby.split("data-nx-open")[0][-80:]
    )
    made = _create(client)
    assert not client.cookies  # no browser store (segment AD2G)
    home = client.get(f"{LOBBY}/{made}").text
    assert "Summer Bursary 2027" in home and "data-scratch-note" not in home
    # On record outside the request: a row, not a browser's (segment AD2G).
    found = sample_data.exercise(made)
    assert found is not None and found.name == "Summer Bursary 2027"
    lobby = client.get(LOBBY).text
    row = lobby[lobby.index(f"/operator/exercises/{made}") :][:800]
    assert "Scratch" not in row and "/discard" not in row
    # Newest first, before the sample.
    assert lobby.index(made) < lobby.index("wa9juxbc2t")
    # Its form is blank (Codex on #4024), and Home says so.
    form = client.get(f"{LOBBY}/{made}/form").text
    assert "Project title" not in form
    assert "Application form" in home
    # Each Setup page renders it (the lookups read its row).
    for section in ("process", "form", "panels", "emails", "dossiers", "evaluations"):
        assert client.get(f"{LOBBY}/{made}/{section}").status_code == 200, section


def test_the_same_operator_in_another_browser_sees_it() -> None:
    """Segment AD2G: an exercise is its row, reached through its grants,
    not one browser's store."""
    mine, theirs = _client(), _client()
    made = _create(mine)
    assert theirs.get(f"{LOBBY}/{made}").status_code == 200
    assert made in theirs.get(LOBBY).text


def test_a_name_is_needed() -> None:
    client = _client()
    refused = client.post(f"{LOBBY}/new", data={"name": "  "})
    assert refused.status_code == 303 and refused.headers["location"].endswith("?said=name_needed")
    long = client.post(f"{LOBBY}/new", data={"name": "x" * 201})
    assert long.headers["location"].endswith("?said=name_long")
    assert "at most 200 characters" in client.get(f"{LOBBY}?said=name_long").text
    assert (
        "A name is needed."
        in client.get(refused.headers["location"].removeprefix("http://testserver")).text
    )


def test_at_most_fifty_live_of_one_s_making(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cap (author, 2026-11-23), here at 3: archived or deleted ones
    free a place; Duplicate counts as New exercise does."""
    monkeypatch.setattr(exercises, "MOST_MADE", 3)
    client = _client()
    made = [_create(client, f"Exercise {n}") for n in range(3)]
    fourth = client.post(f"{LOBBY}/new", data={"name": "One too many"})
    assert fourth.headers["location"].endswith("?said=full")
    full = client.get(fourth.headers["location"].removeprefix("http://testserver")).text
    assert "archive or delete one first" in full
    copy = client.post(f"{LOBBY}/panel", data={"action": "duplicate", "id": made[0]})
    assert copy.headers["location"].endswith("said=full")
    assert (
        client.post(f"{LOBBY}/panel", data={"action": "archive", "id": made[0]}).status_code == 303
    )
    again = _create(client, "Room again")
    assert (
        client.post(f"{LOBBY}/new", data={"name": "Full again"})
        .headers["location"]
        .endswith("?said=full")
    )
    deleted = client.post(
        f"{LOBBY}/panel", data={"action": "delete", "id": again, "confirm": "yes"}
    )
    assert deleted.status_code == 303 and "said=deleted" in deleted.headers["location"]
    _create(client, "Room after a delete")
    # The seeded samples, recorded as made by this same person, never count:
    # they are live and theirs, yet three were made under a cap of 3.
    session = db.new_session()
    try:
        samples = session.scalar(
            select(func.count(Exercise.id)).where(
                Exercise.public_id.in_(sorted(sample_data.SAMPLE_IDS)),
                Exercise.created_by_id.is_not(None),
            )
        )
        assert samples
    finally:
        session.close()


def test_an_allowlisted_operator_is_capped_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """Not only the super-admin: an ordinary operator on the allowlist."""
    monkeypatch.setattr(exercises, "MOST_MADE", 1)
    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", False)
    client = _client()
    _create(client, "Only one")
    assert (
        client.post(f"{LOBBY}/new", data={"name": "Two"}).headers["location"].endswith("?said=full")
    )


def test_someone_off_the_list_is_told_so_not_full(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cold read: the allowlist is checked before the cap."""
    from cordware.identity import Identity

    monkeypatch.setattr(exercises, "MOST_MADE", 0)
    session = db.new_session()
    try:
        stranger = people.resolve(
            session, Identity(principal_id="o-x", email="x@x.edu", name="X", tenant_id="t")
        )
        assert stranger is not None and not operators.may_operate(stranger)
        with pytest.raises(exercises.Refused) as refused:
            exercises.make(session, operators.Actor(stranger), "Not mine to make")
        assert refused.value.key == "not_listed"
    finally:
        session.close()


def test_the_cap_is_fifty() -> None:
    assert exercises.MOST_MADE == 50


def test_the_lobby_status_line_shows_only_its_own_messages() -> None:
    """A key, not text: a crafted link puts no words on the Lobby
    (findings 2026-11-20 S11)."""
    client = _client()
    spoofed = client.get(f"{LOBBY}?said=Your+account+is+locked").text
    assert "data-nx-said" not in spoofed and "account is locked" not in spoofed
    assert "A name is needed." in client.get(f"{LOBBY}?said=name_needed").text


def test_discard_is_retired() -> None:
    """Segment AD2G: *Delete* on the Lobby panel does what *Discard* did."""
    client = _client()
    made = _create(client)
    assert client.post(f"{LOBBY}/{made}/discard").status_code in (404, 405)
    assert client.post(f"{LOBBY}/panel", data={"action": "discard", "id": made}).status_code == 400


def test_an_exercise_survives_a_new_app() -> None:
    """Nothing lives in the process: a restart (a new app on the same
    database) still finds it."""
    made = _create(_client())
    assert _client().get(f"{LOBBY}/{made}").status_code == 200


def test_details_save_into_a_new_exercise() -> None:
    client = _client()
    made = _create(client)
    good = {
        "revision": 0,  # a new exercise has no settings recorded
        "name": "Summer Bursary 2027",
        "code": "SB-27",
        "description": "Bursaries for summer study.",
        "contact": "bursary@example.edu",
        "timezone": "Europe/London",
        "eligibility": "Invitation only",
        "blind": True,
    }
    reply = client.post(f"{LOBBY}/{made}/details", json=good)
    # Recorded (revision 1), then changed (2): segment AD2B rung 3.
    assert reply.status_code == 200 and reply.json() == {"saved": True, "revision": 2}
    good["revision"] = 2
    home = client.get(f"{LOBBY}/{made}").text
    assert "<code>SB-27</code>" in home and "Bursaries for summer study." in home
    assert "Europe/London" in home and "Invitation only" in home
    assert "<code>SB-27</code>" in client.get(LOBBY).text
    for bad, reason in (
        ({**good, "name": ""}, "A name of 1 to 200 characters is needed."),
        ({**good, "code": "ra-2027"}, "already"),
        ({**good, "contact": "not-an-address"}, "A help contact is an email address."),
        ({**good, "timezone": "Mars/Base"}, "That timezone is not offered."),
        ({**good, "blind": "yes"}, "The details are malformed."),
        ({**good, "description": "x" * 2001}, "at most 2,000 characters"),
        ({**good, "revision": "2"}, "The details are malformed."),
    ):
        refused = client.post(f"{LOBBY}/{made}/details", json=bad)
        assert refused.status_code == 400 and reason in refused.json()["error"], bad


def test_a_post_from_another_site_is_refused() -> None:
    client = _client()
    reply = client.post(
        f"{LOBBY}/new", data={"name": "X"}, headers={"Sec-Fetch-Site": "cross-site"}
    )
    assert reply.status_code == 403
    made = _create(client)
    assert (
        client.post(
            f"{LOBBY}/{made}/details", content="{}", headers={"Content-Type": "text/plain"}
        ).status_code
        == 415
    )


def _post_process(client: TestClient, made: str, body: object) -> Any:
    """Process's Save as the page sends it: with the revision the page
    opened at, read off the page, unless the test gives one."""
    if isinstance(body, dict) and "revision" not in body:
        page = client.get(f"{LOBBY}/{made}/process").text
        found = re.search(r'data-revision="(\d+)"', page)
        body = {**body, "revision": int(found.group(1)) if found else 0}  # pyright: ignore[reportUnknownVariableType]  -- a test's dict
    return client.post(f"{LOBBY}/{made}/process", json=body)


def _post_panels(client: TestClient, made: str, body: object) -> Any:
    """Panels' Save as the page sends it: with the revision the page
    opened at, read off the page, unless the test gives one (AD2E)."""
    if isinstance(body, dict) and "revision" not in body:
        page = client.get(f"{LOBBY}/{made}/panels").text
        found = re.search(r'data-revision="(\d+)"', page)
        body = {**body, "revision": int(found.group(1)) if found else 0}  # pyright: ignore[reportUnknownVariableType]  -- a test's dict
    return client.post(f"{LOBBY}/{made}/panels", json=body)


def _post_form(client: TestClient, public_id: str, form: dict[str, Any]) -> Any:
    """Form's Save as the page sends it, with the revision it opened at
    (segment AD2D) unless the test names one."""
    from applydesk import form_store

    sent = {"revision": form_store.revision(public_id), **form}
    return client.post(f"{LOBBY}/{public_id}/form", json=sent)


def _with_form(client: TestClient, made: str) -> None:
    """A Form on the first stage, with its receipt: a new exercise starts
    blank (segment AD2K), so the receipt it owes comes with the Form."""
    form = {"from": "", "to": "", "receipt": True, "reminder": False}
    assert _post_process(client, made, {"stages": [_stage(form=form)]}).status_code == 200


def _post_email(client: TestClient, public_id: str, card: dict[str, Any]) -> Any:
    """An Emails card's Save as the page sends it, with the version of the
    template it opened at (segment AD2L) unless the test names one."""
    from applydesk import email_store

    pair = (card.get("item"), card.get("audience"))
    held = email_store.stored_templates(public_id).get(pair)  # pyright: ignore[reportArgumentType]  -- a test's malformed pair finds none
    sent = {"version": held.version if held else 0, **card}
    return client.post(f"{LOBBY}/{public_id}/emails", json=sent)


def _field(label: str, **over: object) -> dict[str, object]:
    card: dict[str, object] = {
        "kind": "field",
        "type": "string",
        "label": label,
        "help": "",
        "min": "",
        "max": "",
        "step": "",
        "options": "",
        "exclusive": True,
        "required": False,
        "shown": False,
        "pool": "institution",
        "ratio_w": "4",
        "ratio_h": "5",
    }
    card.update(over)
    return card


def test_a_new_exercise_s_form_starts_empty_and_form_saves_into_it() -> None:
    """Rung 3: Form's Save keeps the cards; the page, Preview and Process's
    form-answer rules read them back."""
    client = _client()
    made = _create(client)
    form = client.get(f"{LOBBY}/{made}/form").text
    assert "Project title" not in form  # not the sample's form
    assert "data-fb-save=" in form
    sent = {
        "title": "Bursary application",
        "description": "Tell us about yourself.",
        "cards": [
            {"kind": "section", "label": "About you"},
            _field(
                "Your faculty", type="list", options="Arts, Science, Engineering", required=True
            ),
            _field("Why you", help="A paragraph."),
            {"kind": "pagebreak", "label": ""},
        ],
    }
    reply = _post_form(client, made, sent)
    assert reply.status_code == 200, reply.text
    form = client.get(f"{LOBBY}/{made}/form").text
    assert "Your faculty" in form and "Why you" in form and "Bursary application" in form
    process = client.get(f"{LOBBY}/{made}/process").text
    lists = process.split('id="pc-form-lists">')[1].split("</script>")[0]
    # By the question's key, with its label (segment AD2D).
    assert '{"label": "Your faculty", "options": ["Arts", "Science", "Engineering"]}' in lists
    assert "Application form" not in client.get(f"{LOBBY}/{made}").text  # no longer missing
    preview = client.get(f"{LOBBY}/{made}/form/preview").text
    assert "Your faculty" in preview
    # Another new exercise's form is its own.
    other = _create(client, "Second")
    assert "Your faculty" not in client.get(f"{LOBBY}/{other}/form").text


def test_form_save_is_checked() -> None:
    client = _client()
    made = _create(client)
    for bad, reason in (
        ({"title": "", "description": "", "cards": "x"}, "malformed"),
        ({"title": "", "description": "", "cards": [{"kind": "poster"}]}, "no known kind"),
        # A list or object where a string belongs is a 400, not an
        # unhashable 500 (findings 2026-11-20 S9).
        ({"title": "", "description": "", "cards": [{"kind": ["field"]}]}, "no known kind"),
        (
            {"title": "", "description": "", "cards": [_field("Q", type={"a": 1})]},
            "not one of the choices",
        ),
        (
            {"title": "", "description": "", "cards": [_field("Q", type="essay")]},
            "not one of the choices",
        ),
        ({"title": "", "description": "", "cards": [_field("Q", required="yes")]}, "malformed"),
        ({"title": "", "description": "", "cards": [_field("x" * 501)]}, "too long"),
        (
            {"title": "", "description": "", "cards": [{"kind": "section", "label": "x" * 501}]},
            "too long",
        ),
        ({"title": "x" * 201, "description": "", "cards": []}, "at most 200 characters"),
        (
            {"title": "", "description": "", "cards": [_field("Q", type="people", pool="new-1")]},
            "panel made on this page",
        ),
        ({"title": "", "description": "x" * 4001, "cards": []}, "at most 4,000 characters"),
    ):
        refused = _post_form(client, made, bad)
        assert refused.status_code == 400 and reason in refused.json()["error"], bad
    # A page that sends no revision is refused, not saved over another's.
    assert client.post(f"{LOBBY}/{made}/form", json={"cards": []}).status_code == 400


def _stage(name: str = "", **over: object) -> dict[str, object]:
    st: dict[str, object] = {
        "name": name,
        "from": "",
        "to": "",
        "shown": True,
        "published": False,
        "form": None,
        "gates": [],
        "outcome": None,
    }
    st.update(over)
    return st


def _gate(key: str, label: str, **over: object) -> dict[str, object]:
    g: dict[str, object] = {
        "key": key,
        "label": label,
        "from": "",
        "to": "",
        "description": "",
        "confidential": False,
        "rule": None,
        "mode": "automatic",
        "sources": [{"kind": "panel", "ref": "", "min": 1, "max": 2}],
        "total": {"min": 1, "max": 2},
        "fields": [
            {
                "key": "f1",
                "label": "Rating",
                "type": "integer",
                "min": "1",
                "max": "5",
                "step": "1",
                "options": "",
                "required": True,
                "help": "",
            }
        ],
        "results": [
            {
                "key": "r1",
                "name": "Mean rating",
                "source": "f1",
                "derive": "mean",
                "value": "",
                "at_least": 1,
                "ignore_zero": False,
            }
        ],
    }
    g.update(over)
    return g


def _process() -> dict[str, object]:
    form = {"from": "", "to": "", "receipt": True, "reminder": False}
    outcome = {
        "key": "onew2",
        "label": "Award",
        "due": "2027-03-01T17:00",
        "values": ["Awarded", "Not awarded"],
        "weights": {},
        "rule": {
            "when": [["res", "gnew1.r1", "ge", "3.5"]],
            "then": "Awarded",
            "otherwise": "Not awarded",
        },
        "applicants_email": True,
        "evaluators_email": False,
    }
    return {
        "stages": [
            _stage("Applications", form=form, published=True),
            _stage(
                "Review",
                **{"from": "2027-02-01T09:00", "to": "2027-02-28T17:00"},
                gates=[_gate("gnew1", "Panel read")],
                outcome=outcome,
            ),
        ]
    }


def test_a_new_exercise_starts_with_a_blank_stage() -> None:
    """Segment AD2K rung 2 (ruling 83): one stage, holding nothing, with
    +Form and +Candidates both offered; a sample keeps its form."""
    client = _client()
    made = _create(client)
    cards = _cards(client.get(f"{LOBBY}/{made}/process").text)
    assert cards.count('class="fc pc"') == 1 and "pc-body-empty" in cards
    assert 'data-item="form"' not in cards and 'data-item="candidates"' not in cards
    assert 'data-pc-act="form">+Form</button>' in cards
    assert 'data-pc-act="candidates">+Candidates</button>' in cards
    assert 'data-item="form"' in _cards(client.get(f"{LOBBY}/c4xh2ndv6s/process").text)


def _cards(page: str) -> str:
    """Process's stage cards alone, without the templates +Stage and the
    add buttons clone."""
    return page[page.index('id="pc-cards"') : page.index('<template id="pc-new-stage">')]


def test_process_saves_into_a_new_exercise() -> None:
    """Rung 4: Process's stages, gates, outcomes and ticks kept and read
    back; new keys renumbered, in the rules that name them too."""
    from applydesk import stages, workflow

    client = _client()
    made = _create(client)
    assert (
        'data-fb-snapshot="applydeskProcessSnapshot"' in client.get(f"{LOBBY}/{made}/process").text
    )
    reply = _post_process(client, made, _process())
    assert reply.status_code == 200, reply.text
    process = client.get(f"{LOBBY}/{made}/process").text
    assert 'value="Panel read"' in process and 'data-key="g1"' in process
    assert 'data-key="o1"' in process and "gnew1" not in process and "onew2" not in process
    # The rule follows the gate's new key.
    assert "&#34;g1.r1&#34;" in process or '"g1.r1"' in process
    # Read back outside any request: the saved plan and its ticks.
    plan = stages.plan_of(made)
    assert [st.label for st in plan.stages] == ["Applications", "Review"]
    assert plan.stages[0].status == "Published" and plan.stages[0].form
    assert workflow.sends(made, "receipt", workflow.APPLICANTS)
    assert not workflow.sends(made, "reminder", workflow.APPLICANTS)
    assert workflow.sends(made, "o1", workflow.APPLICANTS)
    assert not workflow.sends(made, "o1", workflow.EVALUATORS)
    # The outcome's email is owed on Emails.
    assert "Award" in client.get(f"{LOBBY}/{made}/emails").text


def test_a_sample_exercise_s_process_saves_into_the_database() -> None:
    """AD2C rung 5: Save is offered on every exercise. A sample's first save
    records its timeline, which its pages read from then on; a stage keeps
    its key; a gate the page adds takes a key past every one the exercise
    has held, and a removed gate's key is never given again."""
    from applydesk import stages

    client = _client()
    model = "wa9juxbc2t"
    page = client.get(f"{LOBBY}/{model}/process").text
    assert "Saving comes with the database" not in page
    assert 'data-fb-save="' in page and 'data-revision="0"' in page
    before = stages.plan_of(model)
    gate_keys = [c.key for c in before.columns if isinstance(c, stages.Gate)]
    two = {
        "stages": [
            _stage("Applications", form={"from": "", "to": "", "receipt": True, "reminder": False}),
            _stage("Review", gates=[_gate(gate_keys[0], "Kept read")]),
        ]
    }
    reply = _post_process(client, model, two)
    assert reply.status_code == 200, reply.text
    stored = stages.plan_of(model)
    assert [st.label for st in stored.stages] == ["Applications", "Review"]
    assert [c.key for c in stored.columns] == [gate_keys[0]]
    assert all(st.key for st in stored.stages)
    page = client.get(f"{LOBBY}/{model}/process").text
    assert 'value="Kept read"' in page and 'data-revision="1"' in page
    assert f'data-stage-key="{stored.stages[0].key}"' in page
    # A gate added on the page: a key past all the sample's, never gnew1.
    top = max(int(k[1:]) for k in gate_keys)
    keyed = [{**st, "key": s.key} for st, s in zip(two["stages"], stored.stages, strict=True)]  # pyright: ignore[reportGeneralTypeIssues, reportUnknownVariableType]  -- a test's dict
    keyed[1]["gates"] = [_gate("gnew1", "Second read")]  # the first gate removed
    assert _post_process(client, model, {"stages": keyed}).status_code == 200
    again = stages.plan_of(model)
    new_key = f"g{top + 1}"
    assert [c.key for c in again.columns] == [new_key]
    assert [st.key for st in again.stages] == [st.key for st in stored.stages]
    # Every page draws the new gate, which no sample cell names: blank.
    for path in ("", "/process", "/form", "/panels", "/emails", "/dossiers", "/evaluations"):
        assert client.get(f"{LOBBY}/{model}{path}").status_code == 200, path
    assert client.get(f"{LOBBY}/{model}/evaluations/{new_key}").status_code == 200
    # Its page is keyed (AD-48): the removed gate's key is not the new
    # gate's, and an old numbered link reaches the gate numbered so now.
    assert client.get(f"{LOBBY}/{model}/evaluations/{gate_keys[0]}").status_code == 404
    old = client.get(f"{LOBBY}/{model}/evaluations/gate_1", follow_redirects=False)
    assert old.status_code == 302
    assert old.headers["location"] == f"{LOBBY}/{model}/evaluations/{new_key}"
    extract = client.get(f"{LOBBY}/{model}/extract")
    assert extract.status_code == 200
    files = set(re.findall(r"/extract/([\w.-]+\.(?:csv|zip))", extract.text))
    assert "all.zip" in files, files  # every gate's file is in it
    for name in sorted(files):
        assert client.get(f"{LOBBY}/{model}/extract/{name}").status_code == 200, name
    session = db.new_session()
    try:
        saves = session.query(AuditEvent).filter_by(event_type="exercise.process_saved").count()
    finally:
        session.close()
    assert saves == 2


def test_a_sample_exercise_adopts_a_panel_made_on_process() -> None:
    """Since AD2E a sample's panels are stored too: a gate naming one made
    on the page keeps it, beside the sample's own panels."""
    client = _client()
    made_panel = {"new-1": {"name": "Readers", "members": [["Ada", "ada@example.edu"]]}}
    gate = _gate("gnew1", "Read", sources=[{"kind": "panel", "ref": "new-1", "min": 1, "max": 1}])
    sent = {
        "stages": [
            _stage(
                "Applications", form={"from": "", "to": "", "receipt": False, "reminder": False}
            ),
            _stage("Review", gates=[gate]),
        ],
        "pools": made_panel,
    }
    kept = _post_process(client, "wa9juxbc2t", sent)
    assert kept.status_code == 200, kept.text
    panels = client.get(f"{LOBBY}/wa9juxbc2t/panels").text
    assert "Readers" in panels and "ada@example.edu" in panels
    assert "Current RAs" in panels  # the sample's own, recorded with it


def test_a_refused_process_save_keeps_no_panel_it_made() -> None:
    """A panel made on Process is stored with the save or not at all: a
    stale save refused after adopting it leaves nothing (AD2E cold read)."""
    from applydesk import panels_store

    client = _client()
    made_panel = {"new-1": {"name": "Readers", "members": [["Ada", "ada@example.edu"]]}}
    gate = _gate("gnew1", "Read", sources=[{"kind": "panel", "ref": "new-1", "min": 1, "max": 1}])
    sent = {"stages": [_stage("Review", gates=[gate])], "pools": made_panel, "revision": 99}
    refused = client.post(f"{LOBBY}/wa9juxbc2t/process", json=sent)
    assert refused.status_code == 409, refused.text
    assert panels_store.revision("wa9juxbc2t") == 0
    assert "Readers" not in client.get(f"{LOBBY}/wa9juxbc2t/panels").text


def test_form_holds_the_exercise_lock_while_it_checks_and_keeps_the_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Panels save cannot retire a panel between Form's check of its
    questions and the form kept: the lock comes first (Codex on #4171); a
    commit that fails puts the form back as it was."""
    from applydesk import panels_store, routes_operator

    client = _client()
    made = _create(client)
    seen: list[str] = []
    real_lock, real_form = panels_store.lock, routes_operator._form  # pyright: ignore[reportPrivateUsage]  -- watched, not replaced
    monkeypatch.setattr(
        panels_store, "lock", lambda s, p: (seen.append("lock"), real_lock(s, p))[1]
    )
    monkeypatch.setattr(
        routes_operator, "_form", lambda *a: (seen.append("form"), real_form(*a))[1]
    )
    form = {"title": "", "description": "", "cards": [_field("Why?")]}
    assert _post_form(client, made, form).status_code == 200
    assert seen[:2] == ["lock", "form"], seen
    kept = client.get(f"{LOBBY}/{made}/form").text
    assert "Why?" in kept

    def fail(self: object) -> None:
        raise OperationalError("COMMIT", {}, Exception("database is locked"))

    from sqlalchemy.orm import Session as OrmSession

    calls = {"n": 0}
    real_commit = OrmSession.commit

    def second_fails(self: OrmSession) -> None:
        calls["n"] += 1
        if calls["n"] == 2:  # the form's commit, after binding the actor
            fail(self)
        real_commit(self)

    monkeypatch.setattr(OrmSession, "commit", second_fails)
    other = {"title": "", "description": "", "cards": [_field("Something else")]}
    assert _post_form(client, made, other).status_code == 409
    monkeypatch.setattr(OrmSession, "commit", real_commit)
    page = client.get(f"{LOBBY}/{made}/form").text
    assert "Why?" in page and "Something else" not in page


def test_a_panels_save_says_its_new_revision() -> None:
    """The page's next Save carries it, so edits kept while a save was on
    its way can be saved next (AD2E cold read)."""
    client = _client()
    made = _create(client)
    first = _post_panels(client, made, _panels())
    assert first.status_code == 200 and first.json()["revision"] == 1
    again = _panels(panels=[{"key": "panel-1", "name": "Readers"}])
    again["people"] = [{**p, "panels": ["panel-1"] if p["panels"] else []} for p in again["people"]]  # pyright: ignore[reportGeneralTypeIssues, reportUnknownVariableType]  -- a test's dict
    second = client.post(f"{LOBBY}/{made}/panels", json={**again, "revision": 1})
    assert second.status_code == 200 and second.json()["revision"] == 2


def test_process_save_is_checked() -> None:
    client = _client()
    made = _create(client)
    two_forms = _process()
    stages_ = two_forms["stages"]
    assert isinstance(stages_, list)
    stages_[1]["form"] = {"from": "", "to": "", "receipt": False, "reminder": False}  # pyright: ignore[reportIndexIssue]  -- a test's dict
    for bad, reason in (
        ({"stages": []}, "at least one stage"),
        ({"stages": "x"}, "malformed"),
        (two_forms, "More than one stage holds the form."),
        ({"stages": [_stage(gates=[_gate("g1", "A", mode="lottery")])]}, "assignment"),
        ({"stages": [_stage(gates=[_gate("G 1", "A")])]}, "key is malformed"),
        (
            {"stages": [_stage(gates=[_gate("g1", "A"), _gate("g1", "B")])]},
            "share a key",
        ),
        ({"stages": [_stage(**{"from": "soon", "to": ""})]}, "not a date"),
        ({"stages": [_stage(**{"from": "2027-02-01T09:00", "to": ""})]}, "both a start and an end"),
        (
            {
                "stages": [
                    _stage(gates=[_gate("g1", "A", **{"from": "", "to": "2027-02-01T09:00"})])
                ]
            },
            "both a start and an end",
        ),
        (
            {
                "stages": [
                    _stage(
                        gates=[
                            _gate(
                                "g1",
                                "A",
                                sources=[{"kind": "panel", "ref": "new-1", "min": 1, "max": 1}],
                            )
                        ]
                    )
                ]
            },
            "panel made on this page",
        ),
        (
            {
                "stages": [
                    _stage(
                        outcome={
                            **_process()["stages"][1]["outcome"],  # pyright: ignore[reportIndexIssue]  -- a test's dict
                            "weights": {"g1.r1": "half"},
                        }
                    )
                ]
            },
            "not all whole percents",
        ),
        (
            {"stages": [_stage(gates=[_gate("g1", "A", results=[{"key": "r1"}] * 4)])]},
            "more than 3",
        ),
    ):
        refused = _post_process(client, made, bad)
        assert refused.status_code == 400 and reason in refused.json()["error"], (
            bad,
            refused.text,
        )
    # A sample exercise saves too since AD2C, at the revision its page opened.
    saved = _post_process(client, "wa9juxbc2t", _process())
    assert saved.status_code == 200, saved.text


def test_a_rule_naming_a_removed_gate_is_refused() -> None:
    """AD2C (AD-62): a rule naming a gate or a result the snapshot drops is
    refused, both named, never kept pointing at nothing; NaN and Infinity
    are refused as weights (Codex on #4026)."""
    client = _client()
    made = _create(client)
    outcome = {
        "key": "o1",
        "label": "Award",
        "due": "",
        "values": ["Yes", "No"],
        "weights": {},
        "rule": {"when": [["res", "g1.r1", "ge", "3"]], "then": "Yes", "otherwise": "No"},
        "applicants_email": False,
        "evaluators_email": False,
    }
    # Gate g1 removed on the page; g2 is all that is left, and the rule
    # still names g1.
    sent = {"stages": [_stage("Review", gates=[_gate("g2", "Second")], outcome=outcome)]}
    refused = _post_process(client, made, sent)
    assert refused.status_code == 400 and "no longer" in refused.json()["error"], refused.text
    # A result removed from a gate still there is refused the same way.
    two = {
        **outcome,
        "rule": {"when": [["res", "g2.r2", "ge", "3"]], "then": "Yes", "otherwise": "No"},
    }
    sent = {"stages": [_stage("Review", gates=[_gate("g2", "Second")], outcome=two)]}
    refused = _post_process(client, made, sent)
    assert refused.status_code == 400 and "no longer" in refused.json()["error"], refused.text
    for bad in ("NaN", "Infinity", "-inf", "33.3", "-5", ""):
        weighed = {**outcome, "weights": {"g2.r1": bad, "g2.r2": "50"}}
        sent = {"stages": [_stage("Review", gates=[_gate("g2", "Second")], outcome=weighed)]}
        refused = _post_process(client, made, sent)
        assert refused.status_code == 400 and "not all whole percents" in refused.json()["error"], (
            bad
        )


def test_an_unfinished_result_saves_and_a_blank_count_is_refused() -> None:
    """Codex on #4026: a result whose field was removed saves as it stands;
    a blank evaluator count is refused, not kept as 0."""
    client = _client()
    made = _create(client)
    loose = {
        "key": "r1",
        "name": "Mean rating",
        "source": "",
        "derive": "",
        "value": "",
        "at_least": 1,
        "ignore_zero": False,
    }
    gate = _gate("g1", "Read", fields=[], results=[loose])
    reply = _post_process(client, made, {"stages": [_stage("R", gates=[gate])]})
    assert reply.status_code == 200, reply.text
    process = client.get(f"{LOBBY}/{made}/process").text
    # No field made up in place of the ones removed (Codex on #4026).
    saved = process[process.index('data-key="g1"') :]
    saved = saved[: saved.index("data-pr-list")]
    assert "No field chosen" in process and "data-rf=" not in saved
    # A gate with no source yet keeps its Total (Codex on #4026).
    bare = _gate("g1", "Read", sources=[], total={"min": 1, "max": 2})
    reply = _post_process(client, made, {"stages": [_stage("R", gates=[bare])]})
    assert reply.status_code == 200, reply.text
    process = client.get(f"{LOBBY}/{made}/process").text
    total = process[process.index('data-ps="total-min"') - 200 :][:600]
    assert 'value="1"' in total and 'value="2"' in total, total
    for sources, total in (
        ([{"kind": "panel", "ref": "", "min": None, "max": 2}], {"min": 1, "max": 2}),
        ([{"kind": "panel", "ref": "", "min": 1, "max": 2}], {"min": 1, "max": None}),
    ):
        blank = _gate("g1", "Read", sources=sources, total=total)
        refused = _post_process(client, made, {"stages": [_stage("R", gates=[blank])]})
        assert refused.status_code == 400 and "whole numbers" in refused.json()["error"]


def _panels(**over: object) -> dict[str, object]:
    sent: dict[str, object] = {
        "panels": [{"key": "made-1", "name": "Readers"}],
        "people": [
            {
                "name": "Ada Reader",
                "email": "ada@example.edu",
                "note": "Chair",
                "panels": ["made-1"],
            },
            {"name": "Ben Spare", "email": "ben@example.edu", "note": "", "panels": []},
        ],
    }
    sent.update(over)
    return sent


def test_panels_save_into_a_new_exercise() -> None:
    """Rung 5: Panels' panels and roster kept; Form and Process pick from
    them; a saved panel keeps its key."""
    client = _client()
    made = _create(client)
    page = client.get(f"{LOBBY}/{made}/panels").text
    assert 'data-fb-snapshot="applydeskPanelsSnapshot"' in page
    reply = _post_panels(client, made, _panels())
    assert reply.status_code == 200, reply.text
    page = client.get(f"{LOBBY}/{made}/panels").text
    assert 'data-panel="panel-1"' in page and "Readers" in page
    # Someone on no panel stays on the roster.
    assert "ben@example.edu" in page and "ada@example.edu" in page
    assert "Readers" in client.get(f"{LOBBY}/{made}/process").text
    # Saved again, the panel keeps its key; renamed, it keeps it too.
    again = _panels(panels=[{"key": "panel-1", "name": "Peer readers"}])
    again["people"] = [{**p, "panels": ["panel-1"] if p["panels"] else []} for p in again["people"]]  # pyright: ignore[reportGeneralTypeIssues, reportUnknownVariableType]  -- a test's dict
    assert _post_panels(client, made, again).status_code == 200
    page = client.get(f"{LOBBY}/{made}/panels").text
    assert 'data-panel="panel-1"' in page and "Peer readers" in page
    # A page that missed its reload sends made-1 again: it is panel-1, not a
    # new key, even once a question uses panel-1 (Codex on #4027).
    form = {
        "title": "",
        "description": "",
        "cards": [_field("Who?", type="people", pool="panel-1")],
    }
    assert _post_form(client, made, form).status_code == 200
    stale = _panels(panels=[{"key": "made-1", "name": "Peer readers"}])
    reply = _post_panels(client, made, stale)
    assert reply.status_code == 200, reply.text
    page = client.get(f"{LOBBY}/{made}/panels").text
    assert 'data-panel="panel-1"' in page and 'data-panel="panel-2"' not in page


def test_panels_save_is_checked() -> None:
    client = _client()
    made = _create(client)
    two = [{"key": "made-1", "name": "Readers"}, {"key": "made-2", "name": "readers"}]
    for bad, reason in (
        ({"panels": "x", "people": []}, "malformed"),
        # A list where a key belongs (findings 2026-11-20 S9).
        (_panels(panels=[{"key": ["made-1"], "name": "Readers"}]), "key"),
        (_panels(panels=two), "Two panels are called"),
        (_panels(panels=[{"key": "made-1", "name": "Email"}]), "CSV column"),
        (_panels(panels=[{"key": "made-1", "name": ""}]), "needs a name"),
        (
            _panels(people=[{"name": "X", "email": "nobody", "note": "", "panels": []}]),
            "no email address",
        ),
        (
            _panels(
                people=[
                    {"name": "X", "email": "x@example.edu", "note": "", "panels": []},
                    {"name": "Y", "email": "X@example.edu", "note": "", "panels": []},
                ]
            ),
            "repeats",
        ),
        (
            _panels(
                people=[{"name": "X", "email": "x@example.edu", "note": "", "panels": ["made-9"]}]
            ),
            "not on the page",
        ),
    ):
        refused = _post_panels(client, made, bad)
        assert refused.status_code == 400 and reason in refused.json()["error"], (bad, refused.text)
    # A panel a question uses cannot be retired.
    assert _post_panels(client, made, _panels()).status_code == 200
    form = {
        "title": "",
        "description": "",
        "cards": [_field("Who?", type="people", pool="panel-1")],
    }
    assert _post_form(client, made, form).status_code == 200
    retired = _post_panels(client, made, _panels(panels=[], people=[]))
    assert retired.status_code == 400 and "in use" in retired.json()["error"]
    # A sample exercise's Panels saves too (AD2E); a page opened before the
    # last save is refused.
    from applydesk import sample_data

    kept = [{"key": p.key, "name": p.name} for p in sample_data.panels_of("wa9juxbc2t")]
    sample = _panels(panels=[*kept, {"key": "made-1", "name": "Readers"}])
    assert _post_panels(client, "wa9juxbc2t", sample).status_code == 200
    stale = client.post(f"{LOBBY}/wa9juxbc2t/panels", json={**sample, "revision": 0})
    assert stale.status_code == 409 and "Reload" in stale.json()["error"]


def test_a_panel_made_on_form_or_process_joins_the_panels() -> None:
    """Rung 5 lifts the refusal Form's and Process's saves had: a panel
    made with +New panel… is kept with the page that names it."""
    client = _client()
    made = _create(client)
    form = {
        "title": "",
        "description": "",
        "cards": [_field("Your referee", type="people", pool="new-1")],
        "pools": {"new-1": {"name": "Referees", "members": [["Cy Ref", "cy@example.edu"]]}},
    }
    reply = _post_form(client, made, form)
    assert reply.status_code == 200 and reply.json()["reload"] is True, reply.text
    # Offered again by a page that missed its reload (Codex on #4027): the
    # panel kept the first time, not a refusal or a second panel.
    again = _post_form(client, made, form)
    assert again.status_code == 200, again.text
    assert 'data-panel="panel-2"' not in client.get(f"{LOBBY}/{made}/panels").text
    panels = client.get(f"{LOBBY}/{made}/panels").text
    assert 'data-panel="panel-1"' in panels and "Referees" in panels and "cy@example.edu" in panels
    assert 'value="panel-1" selected' in client.get(f"{LOBBY}/{made}/form").text
    gate = _gate("gnew1", "Read", sources=[{"kind": "panel", "ref": "new-1", "min": 1, "max": 1}])
    process = {
        "pools": {"new-1": {"name": "Markers", "members": [["Di Mark", "di@example.edu"]]}},
        "stages": [_stage("Review", gates=[gate])],
    }
    reply = _post_process(client, made, process)
    assert reply.status_code == 200, reply.text
    panels = client.get(f"{LOBBY}/{made}/panels").text
    assert 'data-panel="panel-2"' in panels and "Markers" in panels and "Referees" in panels
    # A made panel the post does not carry is refused, not dropped.
    lost = {**form, "pools": {}}
    refused = _post_form(client, made, lost)
    assert refused.status_code == 400 and "panel made on this page" in refused.json()["error"]


def test_an_email_saves_into_a_new_exercise() -> None:
    """Rung 6: an Emails card's template kept by its item and audience;
    written once it has a subject and a body, which the status row follows."""
    client = _client()
    made = _create(client)
    _with_form(client, made)
    page = client.get(f"{LOBBY}/{made}/emails").text
    assert 'data-em-item="receipt"' in page and "data-em-save=" in page
    assert ">Owed<" in page
    reply = _post_email(
        client,
        made,
        {
            "item": "receipt",
            "audience": "Applicants",
            "name": "Stage 1: Receipt · Applicants",
            "revision": 1,
            "subject": "Received: $exercise_name",
            "body": "Dear $applicant_name, thank you.",
        },
    )
    assert reply.status_code == 200, reply.text
    assert reply.json() == {"saved": True, "written": True, "version": 1}
    page = client.get(f"{LOBBY}/{made}/emails").text
    assert 'value="Received: $exercise_name"' in page and "Dear $applicant_name, thank you." in page
    assert ">Written<" in page and ">Owed<" not in page
    # A subject alone keeps it owed.
    reply = _post_email(
        client,
        made,
        {
            "item": "receipt",
            "audience": "Applicants",
            "name": "Stage 1: Receipt · Applicants",
            "revision": 1,
            "subject": "Hi",
            "body": " ",
        },
    )
    assert reply.json() == {"saved": True, "written": False, "version": 2}
    assert ">Owed<" in client.get(f"{LOBBY}/{made}/emails").text


def test_email_save_is_checked() -> None:
    client = _client()
    made = _create(client)
    _with_form(client, made)
    good = {
        "item": "receipt",
        "audience": "Applicants",
        "name": "Stage 1: Receipt · Applicants",
        "revision": 1,
        "subject": "S",
        "body": "B",
    }
    for bad, reason in (
        ({**good, "item": "o9"}, "not one Process owes"),
        ({**good, "name": "Stage 2: Receipt · Applicants"}, "not one Process owes"),
        ({**good, "revision": 2}, "not one Process owes"),
        ({**good, "audience": "Evaluators"}, "not one Process owes"),
        ({**good, "subject": 3}, "malformed"),
        ({**good, "body": "x" * 20001}, "at most"),
        ({**good, "body": "Your outcome: $outcome"}, "$outcome is not a tag"),
    ):
        refused = _post_email(client, made, bad)
        assert refused.status_code == 400 and reason in refused.json()["error"], (bad, refused.text)
    # An unknown tag stays as typed.
    assert _post_email(client, made, {**good, "body": "$nonsense"}).status_code == 200
    # A card opened before another save of the same template is refused
    # (segment AD2L), 409.
    stale = _post_email(client, made, {**good, "version": 0})
    assert stale.status_code == 409 and "Reload" in stale.json()["error"]


def test_templates_keep_their_outcome_and_a_removed_ones_key_is_not_reused() -> None:
    """Cold read, kept since AD2C: removing an earlier outcome leaves the
    later one its key and its template; an outcome added after takes a new
    key, so the removed one's template never lands on it."""
    client = _client()
    made = _create(client)

    def outcome(key: str, label: str) -> dict[str, object]:
        return {
            "key": key,
            "label": label,
            "due": "",
            "values": ["Yes", "No"],
            "weights": {},
            "rule": None,
            "applicants_email": True,
            "evaluators_email": False,
        }

    both = {
        "stages": [
            _stage("Shortlist", outcome=outcome("onew1", "Shortlist")),
            _stage("Award", outcome=outcome("onew2", "Award")),
        ]
    }
    assert _post_process(client, made, both).status_code == 200
    for key, stage, text in (("o1", "Shortlist", "First"), ("o2", "Award", "Second")):
        reply = _post_email(
            client,
            made,
            {
                "item": key,
                "audience": "Applicants",
                "name": f"{stage}: Outcome · Applicants",
                "revision": 1,
                "subject": text,
                "body": text,
            },
        )
        assert reply.status_code == 200, reply.text
    # Shortlist's stage removed: Award's outcome keeps o2 and its template.
    only = {"stages": [_stage("Award", outcome=outcome("o2", "Award"))]}
    assert _post_process(client, made, only).status_code == 200
    page = client.get(f"{LOBBY}/{made}/emails").text
    card = page[page.index('data-em-item="o2"') :][:3000]
    assert 'value="Second"' in card and "First" not in page
    # An outcome added now is o3, never the removed o1.
    again = {
        "stages": [
            _stage("Award", outcome=outcome("o2", "Award")),
            _stage("Appeal", outcome=outcome("onew1", "Appeal")),
        ]
    }
    assert _post_process(client, made, again).status_code == 200
    page = client.get(f"{LOBBY}/{made}/emails").text
    assert 'data-em-item="o3"' in page and 'data-em-item="o1"' not in page
    assert "First" not in page


def test_too_large_a_post_says_so() -> None:
    client = _client()
    made = _create(client)
    huge = {"title": "", "description": "", "cards": [], "pad": "x" * (MAX_BODY + 1)}
    reply = _post_form(client, made, huge)
    assert reply.status_code == 413 and "256 KiB" in reply.json()["detail"]


def test_a_details_refusal_names_its_field() -> None:
    client = _client()
    made = _create(client)
    good = {
        "revision": 0,
        "name": "N",
        "code": "",
        "description": "",
        "contact": "nope",
        "timezone": "Europe/London",
        "eligibility": "Invitation only",
        "blind": False,
    }
    reply = client.post(f"{LOBBY}/{made}/details", json=good)
    assert reply.status_code == 400 and reply.json()["field"] == "contact"


def test_an_emails_page_older_than_process_s_last_save_is_refused() -> None:
    """Codex on #4028: two stages may share a name, so a card opened before
    Process last saved is refused by revision, not judged by its name."""
    client = _client()
    made = _create(client)

    def outcome(key: str) -> dict[str, object]:
        return {
            "key": key,
            "label": "Result",
            "due": "",
            "values": ["Yes", "No"],
            "weights": {},
            "rule": None,
            "applicants_email": True,
            "evaluators_email": False,
        }

    twins = {
        "stages": [
            _stage("Review", outcome=outcome("onew1")),
            _stage("Review", outcome=outcome("onew2")),
        ]
    }
    assert _post_process(client, made, twins).status_code == 200
    assert 'data-em-revision="1"' in client.get(f"{LOBBY}/{made}/emails").text
    only = {"stages": [_stage("Review", outcome=outcome("o2"))]}
    assert _post_process(client, made, only).status_code == 200
    # The first stage's card, opened at revision 1: refused by revision.
    stale = {
        "item": "o1",
        "audience": "Applicants",
        "name": "Review: Outcome · Applicants",
        "revision": 1,
        "subject": "x",
        "body": "x",
    }
    refused = _post_email(client, made, stale)
    assert refused.status_code == 400 and "reload Emails" in refused.json()["error"]
    # The survivor keeps its key, o2 (AD2C): saved at the new revision.
    fresh = {**stale, "item": "o2", "revision": 2}
    assert _post_email(client, made, fresh).status_code == 200


def test_a_process_page_older_than_the_last_save_is_refused() -> None:
    """Codex on #4028: a second tab's older snapshot is refused, never
    merged (ruling 74, as Details is)."""
    client = _client()
    made = _create(client)
    first = {"stages": [_stage("One")], "revision": 0}
    assert client.post(f"{LOBBY}/{made}/process", json=first).status_code == 200
    stale = client.post(f"{LOBBY}/{made}/process", json={**first, "revision": 0})
    assert stale.status_code == 409 and "Reload" in stale.json()["error"], stale.text
    assert client.post(f"{LOBBY}/{made}/process", json={**first, "revision": 1}).status_code == 200


def test_an_ordinary_exercise_published_by_its_stages_fixes_its_code() -> None:
    """Codex on cordware#230: an exercise made with New exercise is built
    a Draft and published by its stages; once one is published, G2 fixes
    its code in the Lobby and on Details, and who may apply on Details,
    as for a sample. Its name and tags still save."""
    from applydesk.lookups import exercise_or_404

    client = _client()
    made = _create(client, "Published by its stages")
    reply = _post_process(client, made, _process())
    assert reply.status_code == 200, reply.text
    shown, revision = exercises.stored_at(exercise_or_404(made))
    assert shown.state == "Draft"  # its own, as built
    details = {
        "revision": revision,
        "name": shown.name,
        "code": "NEW-CODE",
        "description": shown.summary,
        "contact": shown.help_contact,
        "timezone": shown.timezone or sample_data.DEFAULT_TIMEZONE,
        "eligibility": shown.eligibility,
        "blind": shown.blind,
    }
    refused = client.post(f"{LOBBY}/{made}/details", json=details)
    assert refused.status_code == 400 and "Fixed once published" in refused.text
    # The page's controls agree: Details' code and eligibility disabled,
    # the Lobby row marked published (its panel's code then read-only).
    home = client.get(f"{LOBBY}/{made}").text
    assert 'data-dt="code" value="' in home
    code_input = home[home.index('data-dt="code"') :]
    assert code_input[: code_input.index(">")].count("disabled") == 1
    lobby = client.get(LOBBY).text
    row = lobby[lobby.index(f'data-id="{made}"') :]
    assert 'data-published="true"' in row[: row.index(">")]
    session = db.new_session()
    try:
        with pytest.raises(exercises.Refused) as lobby:
            exercises.save_panel(session, made, shown.name, "NEW-CODE", [], revision, None)
        assert lobby.value.key == "code_fixed"
    finally:
        session.rollback()
        session.close()
    session = db.new_session()
    try:
        exercises.save_panel(session, made, "Renamed", shown.code, ["t"], revision, None)
        session.commit()
    finally:
        session.close()
    assert exercises.stored(exercise_or_404(made)).name == "Renamed"
