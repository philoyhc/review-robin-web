"""A gate's Type (segment 23G rung 6, `guide/segment_23G_linked_custom_instrument.md`):
*Review Robin Session* or *Review Robin Session (custom)*, chosen on
Process, saved, shown on the gate card and Evaluations, in
``process.csv``, and sent as the instrument's ``linked_mode``. The RA
exercise's Gate 1 is the custom sample; its note tells *not asked* from
the rest."""

from __future__ import annotations

import csv
import io
import zipfile
from typing import Any

from fastapi.testclient import TestClient

from applydesk import handoff, sample_data, stages
from applydesk.tests._host import host_with

LOBBY = "/applydesk/operator/exercises"
RA = "wa9juxbc2t"


def _client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0], follow_redirects=False)


def _gate(**over: Any) -> dict[str, Any]:
    return {
        "key": "gnew1",
        "label": "Read",
        "from": "",
        "to": "",
        "description": "",
        "confidential": False,
        "rule": None,
        "mode": "automatic",
        "sources": [],
        "total": {"min": 0, "max": 0},
        "fields": [],
        "results": [],
        **over,
    }


def _save(client: TestClient, gate: dict[str, Any]) -> tuple[str, Any]:
    made = client.post(f"{LOBBY}/new", data={"name": "Typed"}).headers["location"]
    made = made.rsplit("/", 1)[-1]
    stage = {
        "name": "Review",
        "from": "",
        "to": "",
        "shown": True,
        "published": False,
        "form": None,
        "gates": [gate],
        "outcome": None,
    }
    return made, client.post(f"{LOBBY}/{made}/process", json={"stages": [stage], "revision": 0})


def test_the_two_types() -> None:
    assert stages.GATE_TYPES == (
        ("RRW", "Review Robin Session"),
        ("RRW-custom", "Review Robin Session (custom)"),
    )


def test_a_saved_gate_keeps_its_type() -> None:
    client = _client()
    made, reply = _save(client, _gate(type="RRW-custom"))
    assert reply.status_code == 200, reply.text
    (gate,) = (c for c in stages.plan_of(made).columns if isinstance(c, stages.Gate))
    assert gate.via == "RRW-custom"
    page = client.get(f"{LOBBY}/{made}/process").text
    assert '<option value="RRW-custom" selected>' in page
    assert "Review Robin Session (custom) · Entry decided by hand" in page


def test_a_gate_without_a_type_is_the_default() -> None:
    gate = _gate()
    made, reply = _save(_client(), gate)
    assert reply.status_code == 200, reply.text
    (saved,) = (c for c in stages.plan_of(made).columns if isinstance(c, stages.Gate))
    assert saved.via == "RRW"


def test_an_unknown_type_is_refused() -> None:
    _, reply = _save(_client(), _gate(type="Paper"))
    assert reply.status_code == 422 or reply.status_code == 400, reply.text
    assert "type is not one of the choices" in reply.text


def test_evaluations_and_process_csv_say_the_type() -> None:
    client = _client()
    page = client.get(f"{LOBBY}/{RA}/evaluations").text
    row = page[page.index('<tr data-gate="g1"') :]
    assert "<td>Review Robin Session (custom)</td>" in row[: row.index("</tr>")]
    row = page[page.index('<tr data-gate="g2"') :]
    assert "<td>Review Robin Session</td>" in row[: row.index("</tr>")]
    z = zipfile.ZipFile(io.BytesIO(client.get(f"{LOBBY}/{RA}/extract/setup.zip").content))
    gates = {
        r["label"]: r["detail"]
        for r in csv.DictReader(io.StringIO(z.read("process.csv").decode("utf-8-sig")))
        if r["kind"] == "gate"
    }
    assert gates["Peer review"].startswith("type=Review Robin Session (custom); ")
    assert gates["Office checks"].startswith("type=Review Robin Session; ")


def test_a_custom_gate_sends_its_mode() -> None:
    exercise = next(e for e in sample_data.exercises() if e.public_id == RA)
    plan = stages.plan_of(RA)
    by_number = {c.number: c for c in plan.columns if isinstance(c, stages.Gate)}

    def settings(gate: stages.Gate) -> dict[str, str]:
        text = handoff.settings_csv(exercise, gate)
        return {r["field"]: r["value"] for r in csv.DictReader(io.StringIO(text))}

    assert settings(by_number[1])["instruments[1].linked_mode"] == "custom"
    assert settings(by_number[2])["instruments[1].linked_mode"] == "locked"


def test_the_custom_sample_says_who_was_not_asked() -> None:
    notes = [r.cells["g1"].note for r in stages.plan_of(RA).rows if r.cells["g1"].value]
    assert any(n.endswith(" not asked") for n in notes)
    assert any(" not asked" not in n for n in notes)
