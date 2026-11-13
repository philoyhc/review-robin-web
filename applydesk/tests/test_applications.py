"""The Applications page (segment AD1C, ruling 13): the model exercise's
rounds of gates and outcomes as columns, every application a row; the
sample's logic (`applydesk/rounds.py`)."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from applydesk import rounds, sample_data
from applydesk.tests._host import host_with

EX = "wa9juxbc2t"
PAGE = f"/applydesk/operator/exercises/{EX}/applications"


@pytest.fixture
def client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0])


def test_the_columns_follow_the_setup(client: TestClient) -> None:
    text = client.get(PAGE).text
    groups = re.findall(r"<th class=\"ap-(?:first|r)\"[^>]*><b>([^<]+)</b>", text)
    assert groups == ["Application stage", "Round 1", "Round 2", "Final"]
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
    assert len(apps) == 101
    assert text.count("data-row ") == len(apps)
    # A submitted application's ID links to its file; a draft's does not.
    assert f'/files/{apps[0].file_id}"><code>{apps[0].public_id}</code></a>' in text
    draft = next(a for a in apps if a.state == "Draft")
    assert f"<code>{draft.public_id}</code></td>" in text


def test_the_model_exercise_reads_as_partway_through() -> None:
    plan = rounds.plan_of(EX)
    by_key = {c.key: c for c in plan.columns}
    assert rounds.counts(plan, by_key["o1"]).startswith("24 shortlisted")
    o1, o2 = by_key["o1"], by_key["o2"]
    assert isinstance(o1, rounds.Outcome) and isinstance(o2, rounds.Outcome)
    assert o1.released and not o2.released
    for row in plan.rows:
        a, cells = row.application, row.cells
        if a.state == "Draft":
            assert all(not c.value for c in cells.values())
        if a.state == "Withdrawn":
            # Keeps what it had; "—" where it was never admitted.
            assert all(not cells[k].value for k in ("g2", "o1", "g3", "o2", "o3"))
            day = int(a.submitted.split()[0])
            assert bool(cells["g1"].value) == (day >= 16)
        if cells["o1"].value == "Not shortlisted":
            assert cells["g3"].value == "Not selected" and not cells["o2"].value
        if cells["o1"].value == "Shortlisted":
            assert cells["o3"].value == "Pending" and cells["o3"].note == "Due 12 Dec"
    notes = {c.note for r in plan.rows for c in r.cells.values()}
    assert {"Excluded: not eligible", "Added by operator: panel request"} <= notes


def test_last_applications_keep_each_applicant_s_last_submitted() -> None:
    plan = rounds.plan_of(EX)
    last = rounds.last_submitted(plan.rows)
    twice = [r.application for r in plan.rows if r.application.applicant == "Chen Farouk"]
    assert [a.state for a in twice] == ["Withdrawn", "Submitted"]
    assert twice[1].public_id in last and twice[0].public_id not in last
    assert len(last) == len({r.application.email for r in plan.rows})


def test_an_exercise_without_rounds_ends_at_status(client: TestClient) -> None:
    text = client.get("/applydesk/operator/exercises/r6tm4kq9wz/applications").text
    assert "data-kind=" not in text
    assert "No rounds yet" in text
