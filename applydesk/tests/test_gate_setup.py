"""Segment AD1O: from a gate's setup on Process to its Review Robin card
(ruling 61), and a whole panel as a source (ruling 62)."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient

from applydesk import scratch
from applydesk.tests._host import host_with

LOBBY = "/applydesk/operator/exercises"


def _client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0], follow_redirects=False)


def test_a_saved_gate_links_to_its_review_robin_card() -> None:
    page = _client().get(f"{LOBBY}/wa9juxbc2t/process").text
    links = re.findall(r'data-pc-rr="[^"]*"><a href="([^"]+)"', page)
    assert links and links[0] == f"{LOBBY}/wa9juxbc2t/evaluations/gate_1#ev-rr", links
    # Each one opens: the card is there.
    client = _client()
    for href in links:
        target = client.get(href.split("#")[0])
        assert target.status_code == 200 and 'id="ev-rr"' in target.text, href
    # A new gate's card (the page's template) says why it has none yet.
    template = page[page.index('id="pc-new-gate"') :]
    assert "once this gate is saved" in template[: template.index("</template>")]


def test_a_draft_s_gate_says_why_it_has_no_link() -> None:
    scratch.clear()
    client = _client()
    made = client.post(f"{LOBBY}/new", data={"name": "Linkless"}).headers["location"]
    made = made.rsplit("/", 1)[-1]
    gate = {
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
    }
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
    reply = client.post(f"{LOBBY}/{made}/process", json={"stages": [stage], "revision": 0})
    assert reply.status_code == 200, reply.text
    page = client.get(f"{LOBBY}/{made}/process").text
    saved = page[page.index('data-key="g1"') :]
    saved = saved[: saved.index("data-pr-list")]
    assert "once the exercise is published" in saved and "/evaluations/gate_" not in saved
    # A new gate in a draft is held back by the draft, not by saving.
    template = page[page.index('id="pc-new-gate"') :]
    assert "once the exercise is published" in template[: template.index("</template>")]
    scratch.clear()


def test_all_takes_the_panel_s_size_as_it_stands() -> None:
    """Ruling 62: an All source's min and max are its panel's size, read
    when the gate is, so the bounds, the summary and the filling follow
    the panel; its typed numbers are kept but unused."""
    from applydesk import sample_data, stages

    gate = stages.Gate(
        "g1",
        1,
        "Read",
        "RRW",
        sources=(stages.Source("panel", "current-ras", 1, 1, all_members=True),),
        total=stages.Total(1, 1),
    )
    size = len(sample_data.panel_pools("wa9juxbc2t")["current-ras"]["members"])
    sources, total = stages.sources_of("wa9juxbc2t", gate)
    assert (sources[0].min, sources[0].max) == (size, size) and sources[0].all_members
    assert stages.total_bounds(sources) == (size, size)
    # Every source taking All: the Total follows too, its typed 1–1 unused,
    # so nothing is left to retype (and nothing to flag).
    assert (total.min, total.max) == (size, size) and not stages.total_problem(sources, total)
    # The filling gives a dossier the whole panel.
    members = tuple(e for _, e in sample_data.panel_pools("wa9juxbc2t")["current-ras"]["members"])
    assert len(stages.fill(sources, total, (members,)).evaluators) == size
    # Beside a source without All, the Total stays the operator's.
    mixed = stages.replace(
        gate,
        sources=(*gate.sources, stages.Source("nominated", "Q", 0, 1)),
        total=stages.Total(1, 1),
    )
    assert stages.sources_of("wa9juxbc2t", mixed)[1] == stages.Total(1, 1)
    # A Nominated source has no All: its numbers stand.
    nominated = stages.replace(
        gate, sources=(stages.Source("nominated", "Q", 0, 1, all_members=True),)
    )
    assert stages.sources_of("wa9juxbc2t", nominated)[0][0].max == 1
    # An empty or missing panel gives 0.
    gone = stages.replace(gate, sources=(stages.Source("panel", "nope", 2, 2, all_members=True),))
    assert stages.sources_of("wa9juxbc2t", gone)[0][0].max == 0


def test_a_sample_gate_naming_a_panel_reads_as_all() -> None:
    page = _client().get(f"{LOBBY}/k7mfr3pq8z/process").text
    assert 'data-ps="all" aria-pressed="true"' in page
    # The header and the Total row carry the column.
    assert "<span>All</span>" in page and '<span class="ps-all"></span>' in page


def test_process_save_keeps_all() -> None:
    from applydesk import stages

    scratch.clear()
    client = _client()
    made = (
        client.post(f"{LOBBY}/new", data={"name": "Wholes"}).headers["location"].rsplit("/", 1)[-1]
    )
    panels = {
        "panels": [{"key": "made-1", "name": "Readers"}],
        "people": [
            {"name": "A", "email": "a@example.edu", "note": "", "panels": ["made-1"]},
            {"name": "B", "email": "b@example.edu", "note": "", "panels": ["made-1"]},
        ],
    }
    assert client.post(f"{LOBBY}/{made}/panels", json=panels).status_code == 200
    gate = {
        "key": "gnew1",
        "label": "Read",
        "from": "",
        "to": "",
        "description": "",
        "confidential": False,
        "rule": None,
        "mode": "automatic",
        "sources": [{"kind": "panel", "ref": "panel-1", "min": 1, "max": 1, "all_members": True}],
        "total": {"min": 2, "max": 2},
        "fields": [],
        "results": [],
    }
    stage = {
        "name": "R",
        "from": "",
        "to": "",
        "shown": True,
        "published": False,
        "form": None,
        "gates": [gate],
        "outcome": None,
    }
    reply = client.post(f"{LOBBY}/{made}/process", json={"stages": [stage], "revision": 0})
    assert reply.status_code == 200, reply.text
    reset = scratch._token.set(client.cookies[scratch.COOKIE])  # pyright: ignore[reportPrivateUsage]  -- the request's context, outside one
    try:
        saved = stages.plan_of(made).columns[0]
        assert isinstance(saved, stages.Gate)
        sources, _ = stages.sources_of(made, saved)
        assert sources[0].all_members and (sources[0].min, sources[0].max) == (2, 2)
    finally:
        scratch._token.reset(reset)  # pyright: ignore[reportPrivateUsage]  -- as above
    bad = {**gate, "sources": [{**gate["sources"][0], "all_members": "yes"}]}  # pyright: ignore[reportIndexIssue]  -- a test's dict
    stage_bad = {**stage, "gates": [bad]}
    refused = client.post(f"{LOBBY}/{made}/process", json={"stages": [stage_bad], "revision": 1})
    assert refused.status_code == 400 and "malformed" in refused.json()["error"]
    scratch.clear()
