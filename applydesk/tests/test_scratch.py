"""Scratch exercises (segment AD1N rung 2, ruling 59): *New exercise*
makes a blank draft held in memory for one browser; Details saves into
it; another browser never sees it."""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from applydesk import sample_data, scratch
from applydesk.tests._host import host_with

LOBBY = "/applydesk/operator/exercises"


@pytest.fixture(autouse=True)
def _empty_store() -> Iterator[None]:
    scratch.clear()
    yield
    scratch.clear()


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
    assert scratch.COOKIE in client.cookies
    home = client.get(f"{LOBBY}/{made}").text
    assert "Summer Bursary 2027" in home and "data-scratch-note" in home
    assert sample_data.exercise(made) is None  # outside a request: no browser
    lobby = client.get(LOBBY).text
    row = lobby[lobby.index(f"/operator/exercises/{made}") :][:800]
    assert "data-scratch-chip>Scratch<" in row and "/discard" in row
    # Newest first, before the sample.
    assert lobby.index(made) < lobby.index("wa9juxbc2t")
    # Its form is blank (Codex on #4024), and Home says so.
    form = client.get(f"{LOBBY}/{made}/form").text
    assert "Project title" not in form
    assert "Application form" in home
    # Each Setup page renders it (the lookups read the scratch first).
    for section in ("process", "form", "panels", "emails", "dossiers", "evaluations"):
        assert client.get(f"{LOBBY}/{made}/{section}").status_code == 200, section


def test_another_browser_cannot_see_or_open_it() -> None:
    mine, theirs = _client(), _client()
    made = _create(mine)
    assert client_404(theirs, f"{LOBBY}/{made}")
    assert made not in theirs.get(LOBBY).text
    assert theirs.post(f"{LOBBY}/{made}/discard").status_code == 404
    assert mine.get(f"{LOBBY}/{made}").status_code == 200


def client_404(client: TestClient, path: str) -> bool:
    return client.get(path).status_code == 404


def test_a_name_is_needed_and_five_at_most() -> None:
    client = _client()
    refused = client.post(f"{LOBBY}/new", data={"name": "  "})
    assert refused.status_code == 303 and "said=" in refused.headers["location"]
    assert (
        "A name is needed."
        in client.get(refused.headers["location"].removeprefix("http://testserver")).text
    )
    for n in range(scratch.LIMIT):
        _create(client, f"Exercise {n}")
    sixth = client.post(f"{LOBBY}/new", data={"name": "One too many"})
    assert "discard+one+first" in sixth.headers["location"]


def test_discard_forgets_it() -> None:
    client = _client()
    made = _create(client)
    reply = client.post(f"{LOBBY}/{made}/discard")
    assert reply.status_code == 303 and "discarded" in reply.headers["location"]
    assert client.get(f"{LOBBY}/{made}").status_code == 404


def test_an_idle_browser_s_scratch_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    made = _create(client)
    later = scratch.time.monotonic() + scratch.IDLE_SECONDS + 1
    monkeypatch.setattr(scratch.time, "monotonic", lambda: later)
    assert client.get(f"{LOBBY}/{made}").status_code == 404


def test_the_cookie_is_renewed_while_the_store_lives() -> None:
    """Codex on #4024: the cookie lasts one idle window from the last
    request, as the store does, not from the exercise's creation."""
    client = _client()
    made = _create(client)
    renewed = client.get(f"{LOBBY}/{made}").headers.get_list("set-cookie")
    assert any(
        c.startswith(f"{scratch.COOKIE}=") and f"Max-Age={scratch.IDLE_SECONDS}" in c
        for c in renewed
    ), renewed
    # A browser with no store is not handed one.
    assert not _client().get(LOBBY).headers.get_list("set-cookie")


def test_details_save_into_the_scratch() -> None:
    client = _client()
    made = _create(client)
    good = {
        "name": "Summer Bursary 2027",
        "code": "SB-27",
        "description": "Bursaries for summer study.",
        "contact": "bursary@example.edu",
        "timezone": "Europe/London",
        "eligibility": "Invitation only",
        "blind": True,
    }
    reply = client.post(f"{LOBBY}/{made}/details", json=good)
    assert reply.status_code == 200 and reply.json() == {"saved": True}
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
    ):
        refused = client.post(f"{LOBBY}/{made}/details", json=bad)
        assert refused.status_code == 400 and reason in refused.json()["error"], bad
    # A sample exercise has no such post.
    assert client.post(f"{LOBBY}/wa9juxbc2t/details", json=good).status_code == 404


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


def test_a_blank_scratch_form_starts_empty_and_form_saves_into_it() -> None:
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
    reply = client.post(f"{LOBBY}/{made}/form", json=sent)
    assert reply.status_code == 200, reply.text
    form = client.get(f"{LOBBY}/{made}/form").text
    assert "Your faculty" in form and "Why you" in form and "Bursary application" in form
    process = client.get(f"{LOBBY}/{made}/process").text
    lists = process.split('id="pc-form-lists">')[1].split("</script>")[0]
    assert '"Your faculty": ["Arts", "Science", "Engineering"]' in lists
    assert "Application form" not in client.get(f"{LOBBY}/{made}").text  # no longer missing
    preview = client.get(f"{LOBBY}/{made}/form/preview").text
    assert "Your faculty" in preview
    # Another scratch exercise's form is its own.
    other = _create(client, "Second")
    assert "Your faculty" not in client.get(f"{LOBBY}/{other}/form").text


def test_form_save_is_checked() -> None:
    client = _client()
    made = _create(client)
    for bad, reason in (
        ({"title": "", "description": "", "cards": "x"}, "malformed"),
        ({"title": "", "description": "", "cards": [{"kind": "poster"}]}, "no known kind"),
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
        refused = client.post(f"{LOBBY}/{made}/form", json=bad)
        assert refused.status_code == 400 and reason in refused.json()["error"], bad
    assert client.post(f"{LOBBY}/wa9juxbc2t/form", json={"cards": []}).status_code == 404


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


def test_process_saves_into_the_scratch() -> None:
    """Rung 4: Process's stages, gates, outcomes and ticks kept and read
    back; new keys renumbered, in the rules that name them too."""
    from applydesk import stages, workflow

    client = _client()
    made = _create(client)
    assert (
        'data-fb-snapshot="applydeskProcessSnapshot"' in client.get(f"{LOBBY}/{made}/process").text
    )
    reply = client.post(f"{LOBBY}/{made}/process", json=_process())
    assert reply.status_code == 200, reply.text
    process = client.get(f"{LOBBY}/{made}/process").text
    assert 'value="Panel read"' in process and 'data-key="g1"' in process
    assert 'data-key="o1"' in process and "gnew1" not in process and "onew2" not in process
    # The rule follows the gate's new key.
    assert "&#34;g1.r1&#34;" in process or '"g1.r1"' in process
    # Read back in a request of this browser: the saved plan and its ticks.
    scratch_token = client.cookies[scratch.COOKIE]
    reset = scratch._token.set(scratch_token)  # pyright: ignore[reportPrivateUsage]  -- the request's context, outside one
    try:
        plan = stages.plan_of(made)
        assert [st.label for st in plan.stages] == ["Applications", "Review"]
        assert plan.stages[0].status == "Published" and plan.stages[0].form
        assert workflow.sends(made, "receipt", workflow.APPLICANTS)
        assert not workflow.sends(made, "reminder", workflow.APPLICANTS)
        assert workflow.sends(made, "o1", workflow.APPLICANTS)
        assert not workflow.sends(made, "o1", workflow.EVALUATORS)
    finally:
        scratch._token.reset(reset)  # pyright: ignore[reportPrivateUsage]  -- as above
    # The outcome's email is owed on Emails.
    assert "Award" in client.get(f"{LOBBY}/{made}/emails").text


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
        refused = client.post(f"{LOBBY}/{made}/process", json=bad)
        assert refused.status_code == 400 and reason in refused.json()["error"], (
            bad,
            refused.text,
        )
    assert client.post(f"{LOBBY}/wa9juxbc2t/process", json=_process()).status_code == 404


def test_a_rule_naming_a_removed_gate_never_reads_another() -> None:
    """Codex on #4026: renumbering never lands a dangling rule on the gate
    renumbered into the removed one's key; NaN and Infinity are refused."""
    from applydesk import stages

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
    assert client.post(f"{LOBBY}/{made}/process", json=sent).status_code == 200
    reset = scratch._token.set(client.cookies[scratch.COOKIE])  # pyright: ignore[reportPrivateUsage]  -- the request's context, outside one
    try:
        plan = stages.plan_of(made)
        gate, kept = plan.columns[0], plan.columns[1]
        assert gate.key == "g1" and isinstance(kept, stages.Outcome) and kept.rule
        assert kept.rule.when[0][1] == "removed.r1"
    finally:
        scratch._token.reset(reset)  # pyright: ignore[reportPrivateUsage]  -- as above
    # A result removed from a gate still there: its rule reads removed too,
    # so a result added later as r2 is not read in its place.
    two = {
        **outcome,
        "rule": {"when": [["res", "g2.r2", "ge", "3"]], "then": "Yes", "otherwise": "No"},
    }
    sent = {"stages": [_stage("Review", gates=[_gate("g2", "Second")], outcome=two)]}
    assert client.post(f"{LOBBY}/{made}/process", json=sent).status_code == 200
    reset = scratch._token.set(client.cookies[scratch.COOKIE])  # pyright: ignore[reportPrivateUsage]  -- as above
    try:
        kept = stages.plan_of(made).columns[1]
        assert isinstance(kept, stages.Outcome) and kept.rule
        assert kept.rule.when[0][1] == "removed.r2"
    finally:
        scratch._token.reset(reset)  # pyright: ignore[reportPrivateUsage]  -- as above
    for bad in ("NaN", "Infinity", "-inf", "33.3", "-5", ""):
        weighed = {**outcome, "weights": {"g2.r1": bad, "g2.r2": "50"}}
        sent = {"stages": [_stage("Review", gates=[_gate("g2", "Second")], outcome=weighed)]}
        refused = client.post(f"{LOBBY}/{made}/process", json=sent)
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
    reply = client.post(f"{LOBBY}/{made}/process", json={"stages": [_stage("R", gates=[gate])]})
    assert reply.status_code == 200, reply.text
    process = client.get(f"{LOBBY}/{made}/process").text
    # No field made up in place of the ones removed (Codex on #4026).
    saved = process[process.index('data-key="g1"') :]
    saved = saved[: saved.index("data-pr-list")]
    assert "No field chosen" in process and "data-rf=" not in saved
    # A gate with no source yet keeps its Total (Codex on #4026).
    bare = _gate("g1", "Read", sources=[], total={"min": 1, "max": 2})
    reply = client.post(f"{LOBBY}/{made}/process", json={"stages": [_stage("R", gates=[bare])]})
    assert reply.status_code == 200, reply.text
    process = client.get(f"{LOBBY}/{made}/process").text
    total = process[process.index('data-ps="total-min"') - 200 :][:600]
    assert 'value="1"' in total and 'value="2"' in total, total
    for sources, total in (
        ([{"kind": "panel", "ref": "", "min": None, "max": 2}], {"min": 1, "max": 2}),
        ([{"kind": "panel", "ref": "", "min": 1, "max": 2}], {"min": 1, "max": None}),
    ):
        blank = _gate("g1", "Read", sources=sources, total=total)
        refused = client.post(
            f"{LOBBY}/{made}/process", json={"stages": [_stage("R", gates=[blank])]}
        )
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


def test_panels_save_into_the_scratch() -> None:
    """Rung 5: Panels' panels and roster kept; Form and Process pick from
    them; a saved panel keeps its key."""
    client = _client()
    made = _create(client)
    page = client.get(f"{LOBBY}/{made}/panels").text
    assert 'data-fb-snapshot="applydeskPanelsSnapshot"' in page
    reply = client.post(f"{LOBBY}/{made}/panels", json=_panels())
    assert reply.status_code == 200, reply.text
    page = client.get(f"{LOBBY}/{made}/panels").text
    assert 'data-panel="panel-1"' in page and "Readers" in page
    # Someone on no panel stays on the roster.
    assert "ben@example.edu" in page and "ada@example.edu" in page
    assert "Readers" in client.get(f"{LOBBY}/{made}/process").text
    # Saved again, the panel keeps its key; renamed, it keeps it too.
    again = _panels(panels=[{"key": "panel-1", "name": "Peer readers"}])
    again["people"] = [{**p, "panels": ["panel-1"] if p["panels"] else []} for p in again["people"]]  # pyright: ignore[reportGeneralTypeIssues, reportUnknownVariableType]  -- a test's dict
    assert client.post(f"{LOBBY}/{made}/panels", json=again).status_code == 200
    page = client.get(f"{LOBBY}/{made}/panels").text
    assert 'data-panel="panel-1"' in page and "Peer readers" in page


def test_panels_save_is_checked() -> None:
    client = _client()
    made = _create(client)
    two = [{"key": "made-1", "name": "Readers"}, {"key": "made-2", "name": "readers"}]
    for bad, reason in (
        ({"panels": "x", "people": []}, "malformed"),
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
        refused = client.post(f"{LOBBY}/{made}/panels", json=bad)
        assert refused.status_code == 400 and reason in refused.json()["error"], (bad, refused.text)
    # A panel a question uses cannot be retired.
    assert client.post(f"{LOBBY}/{made}/panels", json=_panels()).status_code == 200
    form = {
        "title": "",
        "description": "",
        "cards": [_field("Who?", type="people", pool="panel-1")],
    }
    assert client.post(f"{LOBBY}/{made}/form", json=form).status_code == 200
    retired = client.post(f"{LOBBY}/{made}/panels", json=_panels(panels=[], people=[]))
    assert retired.status_code == 400 and "in use" in retired.json()["error"]
    assert client.post(f"{LOBBY}/wa9juxbc2t/panels", json=_panels()).status_code == 404


def test_a_panel_made_on_form_or_process_joins_the_panels() -> None:
    """Rung 5 lifts the refusal Form's and Process's saves had: a panel
    made with + New panel… is kept with the page that names it."""
    client = _client()
    made = _create(client)
    form = {
        "title": "",
        "description": "",
        "cards": [_field("Your referee", type="people", pool="new-1")],
        "pools": {"new-1": {"name": "Referees", "members": [["Cy Ref", "cy@example.edu"]]}},
    }
    reply = client.post(f"{LOBBY}/{made}/form", json=form)
    assert reply.status_code == 200 and reply.json()["reload"] is True, reply.text
    panels = client.get(f"{LOBBY}/{made}/panels").text
    assert 'data-panel="panel-1"' in panels and "Referees" in panels and "cy@example.edu" in panels
    assert 'value="panel-1" selected' in client.get(f"{LOBBY}/{made}/form").text
    gate = _gate("gnew1", "Read", sources=[{"kind": "panel", "ref": "new-1", "min": 1, "max": 1}])
    process = {
        "pools": {"new-1": {"name": "Markers", "members": [["Di Mark", "di@example.edu"]]}},
        "stages": [_stage("Review", gates=[gate])],
    }
    reply = client.post(f"{LOBBY}/{made}/process", json=process)
    assert reply.status_code == 200, reply.text
    panels = client.get(f"{LOBBY}/{made}/panels").text
    assert 'data-panel="panel-2"' in panels and "Markers" in panels and "Referees" in panels
    # A made panel the post does not carry is refused, not dropped.
    lost = {**form, "pools": {}}
    refused = client.post(f"{LOBBY}/{made}/form", json=lost)
    assert refused.status_code == 400 and "panel made on this page" in refused.json()["error"]
