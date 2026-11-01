"""The invite box's directory search (segment 19Z, invite from the
directory, rung 18): sys-admins only; up to ten people whose name,
surname, mail or sign-in name starts with what is typed, from three
characters; "unavailable" when the directory cannot be asked."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.web.routes_operator import _sys_admin

from .test_sys_admin_users import _bootstrap_sys_admin

SEARCH = "/operator/sys-admin/users/directory-search"


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> None:
    from cordware.graph import FakeDirectory

    monkeypatch.setattr(_sys_admin, "directory_or_none", lambda request: FakeDirectory())


def test_a_sys_admin_finds_people_by_name_and_the_address_is_the_mail_else_the_upn(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, fake: None
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    found = client.get(SEARCH, params={"q": "jan"})
    assert found.status_code == 200 and found.headers["cache-control"] == "no-store"
    assert found.json() == {
        "available": True,
        "people": [{"name": "Jane Tan", "mail": "jane.tan@example.edu", "upn": "e0123456@example.edu",
                    "address": "jane.tan@example.edu"}],
    }
    lab = client.get(SEARCH, params={"q": "lab"}).json()["people"]
    assert lab == [{"name": "Lab Account", "mail": None, "upn": "lab01@example.edu", "address": "lab01@example.edu"}]


def test_fewer_than_three_characters_ask_nothing(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, fake: None
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    assert client.get(SEARCH, params={"q": "ja"}).json() == {"available": True, "people": []}


@pytest.mark.parametrize("directory", ["none", "failing"])
def test_a_directory_that_cannot_be_asked_reads_unavailable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, directory: str
) -> None:
    from cordware.graph import FakeDirectory

    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    monkeypatch.setattr(_sys_admin, "directory_or_none", lambda request: None if directory == "none" else FakeDirectory())
    q = "jan" if directory == "none" else "throttled@example.edu"
    assert client.get(SEARCH, params={"q": q}).json() == {"available": False, "people": []}


def test_an_operator_who_is_not_a_sys_admin_is_refused(client: TestClient, fake: None) -> None:
    assert client.get(SEARCH, params={"q": "jan"}).status_code in (403, 404)
