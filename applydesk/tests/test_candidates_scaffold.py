"""AD2C rung 8, the scaffold (rulings 76 and 77): *Open form* and *Close
form* as Home's next step, and the Candidates item on Process, drawn with
their real copy and inert, each saying why."""

from __future__ import annotations

from fastapi.testclient import TestClient

from applydesk.tests._host import host_with

LOBBY = "/applydesk/operator/exercises"


def _client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0], follow_redirects=False)


def test_home_offers_the_form_s_move_inert() -> None:
    client = _client()
    draft = client.get(f"{LOBBY}/c4xh2ndv6s").text
    assert (
        'data-tl-form disabled title="A draft&#39;s form opens once the exercise is published."'
        in draft
    )
    assert ">Open form</button>" in draft
    opened = client.get(f"{LOBBY}/r6tm4kq9wz").text
    assert ">Close form</button>" in opened and "data-tl-form disabled" in opened
    waiting = client.get(f"{LOBBY}/wa9juxbc2t").text
    assert ">Open form</button>" in waiting and "data-tl-form disabled" in waiting


def test_process_offers_candidates_inert() -> None:
    client = _client()
    invited = client.get(f"{LOBBY}/k7mfr3pq8z/process").text
    item = invited[invited.index('data-item="candidates"') :][:3000]
    assert "No candidates yet." in item
    assert "data-cand-search" in item and "data-cand-csv disabled" in item
    assert 'data-pc-act="candidates" disabled' in invited
    # Open to all: no list drawn, the add control still offered (inert).
    open_ = client.get(f"{LOBBY}/wa9juxbc2t/process").text
    assert 'data-item="candidates"' not in open_
    assert 'data-pc-act="candidates" disabled' in open_
