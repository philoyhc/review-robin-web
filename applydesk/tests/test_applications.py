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
PAGE = f"/applydesk/operator/exercises/{EX}/applications"


@pytest.fixture
def client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0])


def test_the_columns_follow_the_setup(client: TestClient) -> None:
    text = client.get(PAGE).text
    groups = re.findall(r"<th class=\"ap-(?:first|r)\"[^>]*><b>([^<]+)</b>", text)
    assert groups == ["Applications", "Review", "Interview", "Decision"]  # ruling 15
    for dates in ("1 Sep – 15 Oct", "16 Oct – 10 Nov", "11 Nov – 24 Nov", "25 Nov – 12 Dec"):
        assert dates in text
    heads = re.findall(r'data-col="(\w+)" data-kind="(\w+)"', text)
    assert heads == [
        ("g1", "gate"),
        ("g2", "gate"),
        ("o1", "outcome"),
        ("g3", "gate"),
        ("o2", "outcome"),
        ("o3", "outcome"),
    ]
    for label in (
        "Peer Review",
        "Faculty Panel Review",
        "Shortlist for interview",
        "Interview",
        "Finalists",
        "Final results",
    ):
        assert label in text


def test_every_application_is_a_row(client: TestClient) -> None:
    text = client.get(PAGE).text
    apps = sample_data.applications_of(EX)
    assert len(apps) == 102
    assert text.count("data-row ") == len(apps)
    # A submitted application's ID links to its file; a draft's does not.
    assert f'/files/{apps[0].file_id}"><code>{apps[0].public_id}</code></a>' in text
    draft = next(a for a in apps if a.state == "Draft")
    assert f"<code>{draft.public_id}</code></td>" in text


def test_the_model_exercise_reads_as_partway_through() -> None:
    plan = stages.plan_of(EX)
    by_key = {c.key: c for c in plan.columns}
    assert stages.counts(plan, by_key["o1"]) == "26 shortlisted · 2 pending"
    assert stages.counts(plan, by_key["g3"]) == "27 entered · 2 to decide"
    o1, o2 = by_key["o1"], by_key["o2"]
    assert isinstance(o1, stages.Outcome) and isinstance(o2, stages.Outcome)
    assert o1.released and not o2.released
    for row in plan.rows:
        a, cells = row.application, row.cells
        if a.state == "Draft":
            assert all(not c.value for c in cells.values())
        if a.state == "Withdrawn":
            # Keeps what it had; "—" where it was never admitted.
            assert all(not cells[k].value for k in ("o1", "g3", "o2", "o3"))
            day = int(a.submitted.split()[0])
            assert bool(cells["g1"].value) == bool(cells["g2"].value) == (day >= 16)
        if cells["o1"].value == "Not shortlisted" and not cells["g3"].by_hand:
            assert cells["g3"].value == "Not entered" and not cells["o2"].value
        if cells["o1"].value == "Shortlisted":
            assert cells["o3"].value == "Pending" and cells["o3"].note == "Due 12 Dec"
        # Where Setup's rule decided it, the outcome follows its combined result.
        comb = stages.combined(row, o1)
        if comb is not None and not cells["o1"].by_hand and cells["o1"].value != "Pending":
            assert (cells["o1"].value == "Shortlisted") == (comb >= 4.2)
    notes = {c.note for r in plan.rows for c in r.cells.values()}
    assert {"Excluded: not eligible", "Added by operator: panel request"} <= notes


def test_last_applications_keep_each_applicant_s_last_submitted() -> None:
    plan = stages.plan_of(EX)
    last = stages.last_submitted(plan.rows)
    twice = [r.application for r in plan.rows if r.application.applicant == "Chen Farouk"]
    assert [a.state for a in twice] == ["Withdrawn", "Submitted"]
    assert twice[1].public_id in last and twice[0].public_id not in last
    assert len(last) == len({r.application.email for r in plan.rows})


def test_an_exercise_with_only_its_first_stage_ends_at_status(client: TestClient) -> None:
    """A new exercise starts with one stage, holding the application,
    named "Stage 1" until the operator names it (ruling 15)."""
    text = client.get("/applydesk/operator/exercises/r6tm4kq9wz/applications").text
    assert "data-kind=" not in text
    assert "No gates or outcomes yet" in text
    assert re.findall(r"<th class=\"ap-first\"[^>]*><b>([^<]+)</b>", text) == ["Stage 1"]


def test_every_sample_s_stages_keep_ruling_15_s_shape() -> None:
    for e in sample_data.EXERCISES:
        assert stages.problems(stages.plan_of(e.public_id).stages) == (), e.public_id


def test_a_stage_may_not_hold_the_application_and_a_gate() -> None:
    gate = stages.Gate("g1", 1, "Panel", "RRW", "Score")
    both = (stages.Stage(1, "", "", (gate,), application=True),)
    two = (
        stages.Stage(1, "A", "", application=True),
        stages.Stage(2, "", "", application=True),
    )
    late = (stages.Stage(1, "", "", (gate,)), stages.Stage(2, "", "", application=True))
    assert stages.problems(both) == ("Stage 1 holds both the application and a gate.",)
    assert "More than one stage holds the application." in stages.problems(two)
    assert stages.problems(late) == ("The stage holding the application is not the first.",)
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
                assert {k for k, _ in c.weights} <= in_scope, c.key
            for kind, key, _, _ in c.rule.when if c.rule else ():
                if kind == "out":
                    assert key in outcomes_before, (c.key, key)
                elif kind in ("res", "ent", "comb"):
                    assert isinstance(c, stages.Outcome), (c.key, kind)
                    assert kind == "comb" or key in in_scope, (c.key, key)
                else:
                    assert kind in ("status", "last"), kind
            seen.add(c.key)


def _with(cells: dict[str, stages.Cell]) -> stages.Row:
    return stages.Row(stages.plan_of(EX).rows[0].application, cells)


def test_a_combined_result_drops_a_gate_not_entered_and_reweights() -> None:
    plan = stages.plan_of(EX)
    o1 = next(c for c in plan.columns if c.key == "o1")
    assert isinstance(o1, stages.Outcome)
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
    for key, gates in (("o1", ["g1", "g2"]), ("o2", ["g3"]), ("o3", [])):
        o = by_key[key]
        assert isinstance(o, stages.Outcome)
        assert [g.key for g in stages.scope(plan, o)] == gates


def test_the_last_submitted_goes_by_date_not_order() -> None:
    plan = stages.plan_of(EX)
    twice = [r for r in plan.rows if r.application.title.startswith("A second proposal")]
    assert len(twice) == 1
    email = twice[0].application.email
    mine = [r for r in plan.rows if r.application.email == email]
    rank = stages.submitted_rank(tuple(reversed(mine)))
    assert rank[twice[0].application.public_id] == 1
    assert sorted(rank.values()) == [1, 2]


def test_a_rule_reads_as_a_line() -> None:
    plan = stages.plan_of(EX)
    by_key = {c.key: c for c in plan.columns}
    assert stages.rule_text(plan, by_key["g1"]) == (
        "Status is Submitted and the applicant's last submitted → Entered, else Not entered"
    )
    assert stages.rule_text(plan, by_key["o2"]) == (
        "Score at Interview ≥ 4.0 → Finalist, else Not a finalist"
    )
    assert stages.rule_text(plan, by_key["o3"]) == ""
    two = stages.Gate(
        "gx",
        9,
        "X",
        "RRW",
        "",
        stages.Rule(
            (("last", "", "le", "2"), ("ent", "g1", "is", "Entered")), "Entered", "Not entered"
        ),
    )
    assert stages.rule_text(plan, two) == (
        "among the applicant's last 2 submitted and Entry at Peer Review is Entered"
        " → Entered, else Not entered"
    )
