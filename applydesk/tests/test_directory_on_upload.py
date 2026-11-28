"""Create dossiers' and Invitees' uploads look each address up in the
directory (segment AD2Y rung 3): those found bound, the rest kept pending
and counted; an expired sign-in saves nothing."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from applydesk import db, directory
from applydesk.models import AuditEvent, Candidate, Invitee, Person
from applydesk.tests._host import host_with
from cordware.graph import DirectoryUser, GraphError

pytestmark = pytest.mark.usefixtures("applydesk_db")

MODEL = "wa9juxbc2t"
LOBBY = "/applydesk/operator/exercises"
FOUND = "aisha.bello@example.edu"  # in the local directory
MISSING = "nobody.here@example.edu"
FILE = f"Name,Email\nAisha,{FOUND}\nNobody,{MISSING}\n"


def _post(path: str, body: dict[str, Any]) -> Any:
    client = TestClient(host_with(("applydesk",))[0], follow_redirects=False)
    return client.post(f"{LOBBY}/{MODEL}/{path}", json=body)


def _person(address: str) -> Person:
    session = db.new_session()
    try:
        found = session.scalar(select(Person).where(Person.email_key == address))
        assert found is not None
        return found
    finally:
        session.close()


def _last(event_type: str) -> dict[str, Any]:
    session = db.new_session()
    try:
        event = session.scalar(
            select(AuditEvent)
            .where(AuditEvent.event_type == event_type)
            .order_by(AuditEvent.id.desc())
        )
        assert event is not None
        return dict(event.detail or {})
    finally:
        session.close()


@pytest.mark.parametrize(("path", "event"), [("candidates", "candidate"), ("invitees", "invitee")])
def test_an_upload_binds_whom_the_directory_finds(path: str, event: str) -> None:
    sent = _post(path, {"action": "csv", "text": FILE})
    assert sent.status_code == 200, sent.text
    reply = sent.json()
    assert reply["said"] == (
        "2 added. Directory: 1 found, 1 not found. Those not found are kept, unverified."
    )
    assert reply["directory"]["directory_by_mail"] == 1
    assert reply["directory"]["directory_not_found"] == 1
    listed = {c["email"]: c["verified"] for c in reply["candidates"]}
    assert listed[FOUND] is True and listed[MISSING] is False
    assert _person(FOUND).object_id and _person(MISSING).object_id is None
    counts = _last(f"{event}.imported")["counts"]
    assert counts["added"] == 2 and counts["directory_not_found"] == 1


class _Expired:
    def find_users(self, address: str) -> list[DirectoryUser]:
        raise GraphError("unauthorized", 401)

    def search_users(self, prefix: str) -> list[DirectoryUser]:
        raise GraphError("unauthorized", 401)


def test_an_expired_sign_in_saves_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(directory, "for_request", lambda request: _Expired())
    sent = _post("candidates", {"action": "csv", "text": FILE})
    assert sent.status_code == 400 and sent.json()["renew"] is True
    assert "Sign in again" in sent.json()["error"]
    session = db.new_session()
    try:
        assert session.scalar(select(func.count()).select_from(Candidate)) == 0
        assert session.scalar(select(Person).where(Person.email_key == MISSING)) is None
    finally:
        session.close()


def test_no_directory_saves_every_address_unchecked(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_token(request: object) -> object:
        raise GraphError("no_token")

    monkeypatch.setattr(directory, "for_request", no_token)
    sent = _post("invitees", {"action": "csv", "text": FILE})
    assert sent.status_code == 200, sent.text
    assert sent.json()["said"] == (
        "2 added. Directory: 0 found, 2 not checked (this sign-in carries no directory access)."
    )
    assert _person(FOUND).object_id is None
    assert _last("invitee.imported")["context"] == {"directory_unchecked": "no_token"}
    session = db.new_session()
    try:
        assert session.scalar(select(func.count()).select_from(Invitee)) == 2
    finally:
        session.close()
