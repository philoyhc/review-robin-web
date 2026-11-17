"""The Applications page (segment AD1C, ruling 13): the model exercise's
stages of gates and outcomes as columns, every application a row; the
sample's logic (`applydesk/stages.py`)."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from applydesk import sample_data, stages
from applydesk.tests._host import host_with

EX = "wa9juxbc2t"
PAGE = f"/applydesk/operator/exercises/{EX}/dossiers"


@pytest.fixture
def client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0])


def test_the_columns_follow_the_setup(client: TestClient) -> None:
    text = client.get(PAGE).text
    groups = re.findall(r"<th class=\"ap-(?:first|r)\"[^>]*><b>([^<]+)</b>", text)
    assert groups == ["Applications", "Review", "Interviews"]  # ruling 15
    for dates in ("1 Sep – 30 Sep", "1 Oct – 6 Nov", "9 Nov – 4 Dec"):
        assert dates in text
    heads = re.findall(r'data-col="(\w+)" data-kind="(\w+)"', text)
    assert heads == [
        ("g1", "gate"),
        ("g2", "gate"),
        ("o1", "outcome"),
        ("g3", "gate"),
        ("o2", "outcome"),
    ]
    for label in ("Peer review", "Office checks", "Shortlisting", "Staff interview", "Selection"):
        assert label in text


def test_every_application_is_a_row(client: TestClient) -> None:
    text = client.get(PAGE).text
    apps = sample_data.applications_of(EX)
    assert len(apps) == 104  # 100 submitted, two drafts and one withdrawn, and Wen's draft
    assert text.count("data-row ") == len(apps)
    # A submitted application's ID links to its dossier; a draft's does not.
    assert f'/dossiers/{apps[0].dossier_id}"><code>{apps[0].public_id}</code></a>' in text
    draft = next(a for a in apps if a.state == "Draft")
    assert f"<code>{draft.public_id}</code></td>" in text


def test_the_model_exercise_reads_as_partway_through() -> None:
    """Ruling 30: the RA recruitment in the middle of Stage 3. One
    application each; every submitted one reviewed and checked; 15 of the
    20 current RAs to re-appointment and 40 new applicants to interview,
    one set by hand; the interviews not yet sent, Selection pending."""
    plan = stages.plan_of(EX)
    by_key = {c.key: c for c in plan.columns}
    assert stages.counts(plan, by_key["g1"]) == "100 entered"
    assert stages.counts(plan, by_key["o1"]) == "15 re-appointment"
    assert stages.counts(plan, by_key["g3"]) == "40 entered"
    assert stages.counts(plan, by_key["o2"]) == "55 pending"
    o1, o2 = by_key["o1"], by_key["o2"]
    assert isinstance(o1, stages.Outcome) and isinstance(o2, stages.Outcome)
    assert o1.released and not o2.released
    ras = {m.email for m in sample_data.CURRENT_RAS}
    decided: dict[str, list[bool]] = {"Re-appointment": [], "Interview": [], "Not shortlisted": []}
    for row in plan.rows:
        a, cells = row.application, row.cells
        if a.state != "Submitted":
            assert all(not c.value for c in cells.values())
            continue
        decided[cells["o1"].value].append(a.email in ras)
        # Where the rule decided it, the cell is what the rule says.
        mean, major = cells["g1"].result, cells["g2"].result
        assert mean is not None and major is not None
        passed = mean >= 3.5 and major < 1
        rule = (
            ("Re-appointment" if a.email in ras else "Interview") if passed else "Not shortlisted"
        )
        if not cells["o1"].by_hand:
            assert cells["o1"].value == rule, a.public_id
        entered = cells["o1"].value == "Interview"
        assert cells["g3"].value == ("Entered" if entered else "Not entered")
        reached = cells["o1"].value != "Not shortlisted"
        assert cells["o2"].value == ("Pending" if reached else "")
    assert decided["Re-appointment"] == [True] * 15
    assert decided["Interview"] == [False] * 40
    assert decided["Not shortlisted"].count(True) == 5
    hand = [r for r in plan.rows if r.cells["o1"].by_hand]
    assert len(hand) == 1 and hand[0].cells["o1"].note == "Set by hand: panel request"
    # Gate 1's note says how many scored: those who did not know them left out.
    aisha = next(r for r in plan.rows if r.application.public_id == "m3qx8vkt2n")
    assert re.fullmatch(r"\d\.\d from \d+ of 29", aisha.cells["g1"].note)
    assert aisha.cells["o1"].value == "Re-appointment"
    kenji = next(r for r in plan.rows if r.application.public_id == "h6zr2tdw9p")
    assert kenji.cells["o1"].value == "Interview" and kenji.cells["g1"].note.endswith("of 30")


def _app(i: str, email: str, state: str, day: int) -> sample_data.Application:
    return sample_data.Application(i, EX, "X", email, "", state, f"{day} Sep 2026", "d" + i)


def test_last_applications_keep_each_applicant_s_last_submitted() -> None:
    """A gate may take an applicant's last submitted (author, 2026-11-13);
    the RA recruitment takes one each, so this reads made-up rows."""
    rows = tuple(
        stages.Row(a, {})
        for a in (
            _app("a1", "x@e.edu", "Withdrawn", 3),
            _app("a2", "x@e.edu", "Submitted", 5),
            _app("a3", "y@e.edu", "Draft", 4),
        )
    )
    last = stages.last_submitted(rows)
    assert last == frozenset({"a2", "a3"})


def test_an_exercise_with_only_its_first_stage_ends_at_status(client: TestClient) -> None:
    """A new exercise starts with one stage, holding the application,
    named "Stage 1" until the operator names it (ruling 15)."""
    text = client.get("/applydesk/operator/exercises/r6tm4kq9wz/dossiers").text
    assert "data-kind=" not in text
    assert "No gates or outcomes yet" in text
    assert re.findall(r"<th class=\"ap-first\"[^>]*><b>([^<]+)</b>", text) == ["Stage 1"]


def test_every_sample_s_stages_keep_ruling_15_s_shape() -> None:
    for e in sample_data.EXERCISES:
        assert stages.problems(stages.plan_of(e.public_id).stages) == (), e.public_id


def test_a_stage_may_not_hold_the_application_and_a_gate() -> None:
    gate = stages.Gate("g1", 1, "Panel", "RRW")
    both = (stages.Stage(1, "", "", (gate,), form=True),)
    two = (
        stages.Stage(1, "A", "", form=True),
        stages.Stage(2, "", "", form=True),
    )
    late = (stages.Stage(1, "", "", (gate,)), stages.Stage(2, "", "", form=True))
    assert stages.problems(both) == ("Stage 1 holds both the form and a gate.",)
    assert "More than one stage holds the form." in stages.problems(two)
    assert stages.problems(late) == ()  # a gate may come first (author, 2026-11-13)
    assert stages.problems((stages.Stage(1, "", "", (gate,)),)) == ()  # from elsewhere


# --- Rung 6: rules set on Setup (ruling 13) ---
def test_every_rule_reads_only_what_its_column_may() -> None:
    """A gate reads status, last submitted and earlier outcomes, never a
    gate; an outcome reads the gates in its scope and earlier outcomes;
    weights cover only its scope."""
    for ex in (EX, "k7mfr3pq8z"):
        plan = stages.plan_of(ex)
        seen: set[str] = set()
        for c in plan.columns:
            outcomes_before = {
                k
                for k in seen
                if isinstance(next(x for x in plan.columns if x.key == k), stages.Outcome)
            }
            in_scope = (
                {g.key for g in stages.scope(plan, c)} if isinstance(c, stages.Outcome) else set()
            )
            if isinstance(c, stages.Outcome):
                # A weight names a gate's result, "g1.r1" (ruling 21).
                assert {stages.split_key(k)[0] for k, _ in c.weights} <= in_scope, c.key
            for kind, key, _, _ in (
                (k for when, _ in c.rule.branches for k in when) if c.rule else ()
            ):
                if kind == "out":
                    assert key in outcomes_before, (c.key, key)
                elif kind in ("res", "ent", "comb"):
                    assert isinstance(c, stages.Outcome), (c.key, kind)
                    assert kind == "comb" or stages.split_key(key)[0] in in_scope, (c.key, key)
                elif kind == "top":
                    assert isinstance(c, stages.Outcome), (c.key, kind)
                    assert stages.split_key(key)[0] in in_scope, (c.key, key)
                else:
                    assert kind in ("status", "last", "form"), kind
            seen.add(c.key)


def _with(cells: dict[str, stages.Cell]) -> stages.Row:
    return stages.Row(stages.plan_of(EX).rows[0].application, cells)


def test_a_combined_result_drops_a_gate_not_entered_and_reweights() -> None:
    o1 = stages.Outcome("o1", 1, "X", ("Yes", "No"), "", "", (("g1", 0.3), ("g2", 0.7)))
    both = _with(
        {"g1": stages.Cell("Entered", result=4.0), "g2": stages.Cell("Entered", result=5.0)}
    )
    assert stages.combined(both, o1) == 4.7
    one = _with({"g1": stages.Cell("Not entered"), "g2": stages.Cell("Entered", result=3.5)})
    assert stages.combined(one, o1) == 3.5
    waiting = _with({"g1": stages.Cell("Entered"), "g2": stages.Cell("Entered", result=3.5)})
    assert stages.combined(waiting, o1) is None
    undecided = _with(
        {"g1": stages.Cell(stages.NO_STATUS), "g2": stages.Cell("Entered", result=3.5)}
    )
    assert stages.combined(undecided, o1) is None
    neither = _with({"g1": stages.Cell("Not entered"), "g2": stages.Cell("Not entered")})
    assert stages.combined(neither, o1) is None


def test_scope_is_the_gates_since_the_previous_outcome() -> None:
    plan = stages.plan_of(EX)
    by_key = {c.key: c for c in plan.columns}
    for key, gates in (("o1", ["g1", "g2"]), ("o2", ["g3"])):
        o = by_key[key]
        assert isinstance(o, stages.Outcome)
        assert [g.key for g in stages.scope(plan, o)] == gates


def test_the_last_submitted_goes_by_date_not_order() -> None:
    mine = (_app("b2", "z@e.edu", "Submitted", 20), _app("b1", "z@e.edu", "Submitted", 9))
    rank = stages.submitted_rank(tuple(stages.Row(a, {}) for a in mine))
    assert rank == {"b2": 1, "b1": 2}


def test_a_rule_reads_as_a_line() -> None:
    plan = stages.plan_of(EX)
    by_key = {c.key: c for c in plan.columns}
    assert stages.rule_text(plan, by_key["g1"]) == "Status is Submitted → Entered, else Not entered"
    assert stages.rule_text(plan, by_key["g3"]) == (
        "Shortlisting is Interview → Entered, else Not entered"
    )
    two = stages.Gate(
        "gx",
        9,
        "X",
        "RRW",
        rule=stages.Rule(
            (("last", "", "le", "2"), ("ent", "g1", "is", "Entered")), "Entered", "Not entered"
        ),
    )
    assert stages.rule_text(plan, two) == (
        "among the applicant's last 2 submitted and Entry at Peer review is Entered"
        " → Entered, else Not entered"
    )


def test_a_rule_branches_and_reads_a_form_answer_and_the_best_n() -> None:
    """Ruling 30: further branches tried in order, an answer to a List
    question, the best N by a result; the model exercise's two rules as
    lines, and one as JSON."""
    plan = stages.plan_of(EX)
    by_key = {c.key: c for c in plan.columns}
    assert stages.rule_text(plan, by_key["o1"]) == (
        "Mean score at Peer review ≥ 3.5 and Major concerns at Office checks < 1 and"
        " Currently an RA? is Yes → Re-appointment; else if Mean score at Peer review ≥ 3.5"
        " and Major concerns at Office checks < 1 → Interview, else Not shortlisted"
    )
    assert stages.rule_text(plan, by_key["o2"]) == (
        "Shortlisting is Re-appointment → Selected; else if Shortlisting is Interview and"
        " the best 20 by Interview score at Staff interview → Selected, else Not selected"
    )
    o2 = by_key["o2"]
    assert o2.rule is not None and [then for _, then in o2.rule.branches] == ["Selected"] * 2
    assert stages.rule_json(o2) == {
        "when": [["out", "o1", "is", "Re-appointment"]],
        "then": "Selected",
        "otherwise": "Not selected",
        "more": [
            {
                "when": [["out", "o1", "is", "Interview"], ["top", "g3.r1", "le", "20"]],
                "then": "Selected",
            }
        ],
    }
    # A one-branch rule's JSON is as before: the page's editor reads it.
    assert "more" not in (stages.rule_json(by_key["g3"]) or {})


def test_an_application_answers_the_form_s_list_questions() -> None:
    """Ruling 30's form answers: whether one is a current RA, and their
    house, are what the sample knows; the rest seeded."""
    apps = [a for a in sample_data.applications_of(EX) if a.state == "Submitted"]
    got = [sample_data.answers(EX, a) for a in apps]
    assert set(got[0]) == {"Year of study", "Faculty", "Currently an RA?", "Residence"}
    ras = {m.email for m in sample_data.CURRENT_RAS}
    assert [g["Currently an RA?"] == "Yes" for g in got] == [a.email in ras for a in apps]
    assert sum(g["Currently an RA?"] == "Yes" for g in got) == 20
    assert all(a.title.endswith(g["Residence"]) for a, g in zip(apps, got, strict=True))
    assert len({g["Faculty"] for g in got}) > 3  # spread, not one
    assert got == [sample_data.answers(EX, a) for a in apps]  # seeded
    assert sample_data.answers("n5wg8tjr3e", apps[0]) == {}  # no questions


def test_a_rule_reads_as_the_process_page_s_script_does_at_the_edges() -> None:
    """A column gone, one unnamed, a gate with no measure and a blank
    decision read as `_process.html`'s `condText` and `ruleText` write them."""
    plan = stages.plan_of(EX)
    blank = stages.Gate("gb", 9, "", "")
    rule = stages.Rule(
        (("res", "gb", "ge", "3"), ("ent", "gone", "is", "Entered"), ("out", "o1", "is", "")),
        "",
        "",
    )
    o = stages.Outcome("ox", 9, "X", (), "", "", rule=rule)
    stub = stages.Stage(9, "", "", (blank, o))
    with_blank = stages.Plan((*plan.stages, stub), plan.rows)
    assert stages.rule_text(with_blank, o) == (
        "Result at Untitled gate ≥ 3 and Entry at (removed) is Entered"
        " and Shortlisting is — → —, else —"
    )


def test_a_stage_holds_one_outcome_at_most() -> None:
    o = stages.Outcome("o1", 1, "A", ("Yes",), "", "")
    two = (stages.Stage(1, "", "", (o, o)),)
    assert stages.problems(two) == ("Stage 1 holds more than one outcome.",)
    with_application = (stages.Stage(1, "Applications", "", (o,), form=True),)
    assert stages.problems(with_application) == ()
