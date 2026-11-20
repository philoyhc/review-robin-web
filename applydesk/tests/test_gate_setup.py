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
