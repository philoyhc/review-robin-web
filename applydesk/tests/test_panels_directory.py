"""Panels and the directory (segment AD2Y rung 4a): the typeahead's search,
the lookup a CSV or a typed address asks, and Save binding the members the
directory finds."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from applydesk import db, directory
from applydesk.models import Exercise, Person
from applydesk.tests._host import host_with
from cordware.graph import DirectoryUser, GraphError

pytestmark = pytest.mark.usefixtures("applydesk_db")

LOBBY = "/applydesk/operator/exercises"
BASE = f"{LOBBY}/wa9juxbc2t/panels"
FOUND = "arun.kumar@example.edu"  # in the fake directory, in no sample
MISSING = "nobody.here@example.edu"


def _client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0], follow_redirects=False)


def test_the_typeahead_searches_the_directory() -> None:
    reply = _client().get(f"{BASE}/search", params={"q": "arun"})
    assert reply.status_code == 200
    assert ["Arun Kumar", FOUND] in reply.json()["people"]


def test_a_lookup_names_those_found_and_saves_nothing() -> None:
    reply = _client().post(f"{BASE}/lookup", json={"addresses": [FOUND, MISSING]})
    assert reply.status_code == 200, reply.text
    body = reply.json()
    assert body["found"] == {FOUND: ["Arun Kumar", FOUND]}
    assert body["said"].startswith("Directory: 1 found, 1 not found.")
    session = db.new_session()
    try:
        assert session.scalar(select(Person).where(Person.email_key == FOUND)) is None
    finally:
        session.close()


def _made(client: TestClient) -> str:
    made = client.post(f"{LOBBY}/new", data={"name": "Directory panels"})
    return made.headers["location"].rsplit("/", 1)[-1]


def _revision(public_id: str) -> int:
    session = db.new_session()
    try:
        return (
            session.scalar(select(Exercise.panels_revision).where(Exercise.public_id == public_id))
            or 0
        )
    finally:
        session.close()


def _snapshot(public_id: str) -> dict[str, Any]:
    return {
        "revision": _revision(public_id),
        "panels": [{"key": "made-1", "name": "Readers"}],
        "people": [
            {"name": "Arun", "email": FOUND, "note": "", "panels": ["made-1"]},
            {"name": "Nobody", "email": MISSING, "note": "", "panels": ["made-1"]},
        ],
    }


def _person(address: str) -> Person:
    session = db.new_session()
    try:
        found = session.scalar(select(Person).where(Person.email_key == address))
        assert found is not None
        return found
    finally:
        session.close()


def test_save_binds_the_members_the_directory_finds() -> None:
    client = _client()
    made = _made(client)
    reply = client.post(f"{LOBBY}/{made}/panels", json=_snapshot(made))
    assert reply.status_code == 200, reply.text
    assert _person(FOUND).object_id and _person(MISSING).object_id is None


class _Expired:
    def find_users(self, address: str) -> list[DirectoryUser]:
        raise GraphError("unauthorized", 401)

    def search_users(self, prefix: str) -> list[DirectoryUser]:
        raise GraphError("unauthorized", 401)


def test_an_expired_sign_in_saves_no_panels(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _client()
    made = _made(client)
    monkeypatch.setattr(directory, "for_request", lambda request: _Expired())
    reply = client.post(f"{LOBBY}/{made}/panels", json=_snapshot(made))
    assert reply.status_code == 400 and reply.json()["renew"] is True
    assert _revision(made) == 0


def test_a_bound_roster_asks_the_directory_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Members already bound cost no lookup on a later save."""
    client = _client()
    made = _made(client)
    assert client.post(f"{LOBBY}/{made}/panels", json=_snapshot(made)).status_code == 200
    asked: list[str] = []

    class _Counting:
        def find_users(self, address: str) -> list[DirectoryUser]:
            asked.append(address)
            return []

        def search_users(self, prefix: str) -> list[DirectoryUser]:
            return []

    monkeypatch.setattr(directory, "for_request", lambda request: _Counting())
    assert client.post(f"{LOBBY}/{made}/panels", json=_snapshot(made)).status_code == 200
    assert asked == [MISSING]
