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
