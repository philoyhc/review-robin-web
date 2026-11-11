"""The handoff create route (segment 23A, rung 2;
`guide/segment_23A_interop_poc.md`): another Cordware application's
rosters become a draft session, all or nothing, and nothing else
happens."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    AuditEvent,
    EmailOutbox,
    Invitation,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.web import views
from app.web.routes_operator import _quick_setup

URL = "/operator/handoffs/sessions"
REVIEWERS = (
    "ReviewerName,ReviewerEmail,ReviewerTag1\r\n"
    "Ada,ada@example.edu,Panel A\r\n"
    "Ben,ben@example.edu,Panel A\r\n"
)
REVIEWEES = (
    "RevieweeName,RevieweeEmail,RevieweeTag1,ProfileLink\r\n"
    "Dana,SCH27-0001,Science,https://applydesk.invalid/review/SCH27-0001\r\n"
    "Eli,SCH27-0002,Arts,https://applydesk.invalid/review/SCH27-0002\r\n"
    "Fay,SCH27-0003,Arts,https://applydesk.invalid/review/SCH27-0003\r\n"
)


def _bundle(**changes: Any) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "protocol": "cordware.csv-handoff",
        "protocol_version": 1,
        "operation": "reviewrobin.create_draft_session",
        "source_app": "utilities",
        "transfer_id": str(uuid.uuid4()),
        "session_suggestion": {"name": "Mock Scholarship 2027", "code": "POC-TEST-1"},
        "files": {"reviewers": REVIEWERS, "reviewees": REVIEWEES},
    }
    bundle.update(changes)
    return bundle


def _post(client: TestClient, bundle: dict[str, Any], **headers: str):
    return client.post(
        URL,
        content=json.dumps(bundle),
        headers={"Content-Type": "application/json", "Sec-Fetch-Site": "same-origin", **headers},
    )


def _count(db: Session, model: Any) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_a_handoff_creates_a_populated_draft_and_nothing_else(
    client: TestClient, db: Session
) -> None:
    reply = _post(client, _bundle())
    assert reply.status_code == 201, reply.text
    assert reply.headers["cache-control"] == "no-store"
    receipt = reply.json()
    assert receipt["status"] == "created"
    assert receipt["session_code"] == "POC-TEST-1"
    assert receipt["session_home_url"] == f"/operator/sessions/{receipt['session_ref']}"
    review_session = db.scalars(
        select(ReviewSession).where(ReviewSession.code == "POC-TEST-1")
    ).one()
    assert review_session.status == "draft"
    assert _count(db, Reviewer) == 2 and _count(db, Reviewee) == 3
    reviewee = db.scalars(
        select(Reviewee).where(Reviewee.email_or_identifier == "SCH27-0001")
    ).one()
    assert reviewee.profile_link == "https://applydesk.invalid/review/SCH27-0001"
    # No implicit work progression (interop spec §3 invariant 4).
    assert _count(db, Assignment) == 0
    assert _count(db, Invitation) == 0
    assert _count(db, EmailOutbox) == 0
    event = db.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "session.handoff_created")
    ).one()
    assert event.detail is not None
    assert event.detail["context"]["source_app"] == "utilities"
    assert event.detail["counts"] == {"files": 2}


def test_the_receipt_url_carries_the_mount_prefix(
    mounted_client: TestClient,
) -> None:
    reply = mounted_client.post(
        "/reviewrobin" + URL,
        content=json.dumps(_bundle()),
        headers={"Content-Type": "application/json"},
    )
    assert reply.status_code == 201, reply.text
    assert reply.json()["session_home_url"].startswith("/reviewrobin/operator/sessions/")


def test_a_replay_returns_the_same_session(client: TestClient, db: Session) -> None:
    bundle = _bundle()
    first = _post(client, bundle).json()
    again = _post(client, bundle)
    assert again.status_code == 200
    assert again.json()["status"] == "already_created"
    assert again.json()["session_ref"] == first["session_ref"]
    assert _count(db, ReviewSession) == 1


def test_another_users_replay_is_a_conflict(
    client: TestClient,
    make_client: Callable[[AuthenticatedUser], TestClient],
    bob: AuthenticatedUser,
    db: Session,
) -> None:
    bundle = _bundle()
    assert _post(client, bundle).status_code == 201
    other = _post(make_client(bob), bundle)
    assert other.status_code == 409 and other.json()["error"] == "duplicate_conflict"
    assert _count(db, ReviewSession) == 1


def test_a_refused_roster_leaves_no_session_and_says_why(client: TestClient, db: Session) -> None:
    bad = "ReviewerName,ReviewerEmail\r\nAda,not-an-address\r\nAda,not-an-address\r\n"
    bundle = _bundle(files={"reviewers": bad, "reviewees": REVIEWEES})
    reply = _post(client, bundle)
    assert reply.status_code == 422
    body = reply.json()
    assert body["error"] == "invalid_setup" and body["slot"] == "reviewers"
    assert body["reason"] and body.get("details")
    assert _count(db, ReviewSession) == 0
    assert _count(db, Reviewer) == 0 and _count(db, Reviewee) == 0
    # A refused transfer may be sent again once fixed.
    fixed = _post(client, {**bundle, "files": {"reviewers": REVIEWERS, "reviewees": REVIEWEES}})
    assert fixed.status_code == 201


def test_a_taken_code_is_a_conflict(client: TestClient, db: Session) -> None:
    assert _post(client, _bundle()).status_code == 201
    second = _post(client, _bundle())
    assert second.status_code == 409 and second.json()["error"] == "session_code_conflict"
    assert _count(db, ReviewSession) == 1


def test_the_envelope_is_checked(client: TestClient, db: Session) -> None:
    cases: list[tuple[dict[str, Any], int, str]] = [
        (_bundle(protocol_version=2), 422, "unsupported_version"),
        (_bundle(operation="reviewrobin.replace_session"), 422, "unsupported_version"),
        (_bundle(transfer_id="not-a-uuid"), 422, "invalid_package"),
        (_bundle(files={"reviewers": REVIEWERS}), 422, "invalid_package"),
        (
            _bundle(files={"reviewers": REVIEWERS, "reviewees": REVIEWEES, "settings": "x"}),
            422,
            "invalid_package",
        ),
        (_bundle(session_suggestion={"name": "", "code": "X"}), 422, "invalid_package"),
    ]
    for bundle, status_code, code in cases:
        reply = _post(client, bundle)
        assert (reply.status_code, reply.json()["error"]) == (status_code, code), bundle
    assert _count(db, ReviewSession) == 0


def test_only_json_from_the_same_site(client: TestClient, db: Session) -> None:
    as_form = client.post(URL, data={"x": "1"})
    assert as_form.status_code == 415
    for site in ("cross-site", "same-site", "none"):
        cross = _post(client, _bundle(), **{"Sec-Fetch-Site": site})
        assert cross.status_code == 403 and cross.json()["error"] == "not_authorized", site
    garbled = client.post(URL, content=b"{not json", headers={"Content-Type": "application/json"})
    assert garbled.status_code == 422
    assert _count(db, ReviewSession) == 0


def test_an_oversized_body_is_refused(client: TestClient, db: Session) -> None:
    huge = _bundle(files={"reviewers": REVIEWERS + "x" * (1024 * 1024), "reviewees": REVIEWEES})
    assert _post(client, huge).status_code == 413
    assert _count(db, ReviewSession) == 0


def test_a_non_operator_is_turned_away(
    make_client: Callable[[AuthenticatedUser], TestClient], db: Session
) -> None:
    stranger = AuthenticatedUser(
        principal_id="zed-oid", email="zed@example.edu", name="Zed", provider="aad"
    )
    reply = _post(make_client(stranger), _bundle())
    # The package gate's usual answer: a 303 to /me (followed here). The
    # sending page asks with ``redirect: "manual"`` and reads it as
    # not authorized (rung 3).
    assert reply.history and reply.history[0].status_code == 303
    assert "/me" in reply.history[0].headers["location"]
    assert _count(db, ReviewSession) == 0


def test_a_deeply_nested_body_is_refused_not_a_500(client: TestClient, db: Session) -> None:
    deep = "[" * 200_000
    reply = client.post(URL, content=deep, headers={"Content-Type": "application/json"})
    assert reply.status_code == 422 and reply.json()["error"] == "invalid_package"


def test_an_undeclared_length_is_refused_unread(client: TestClient, db: Session) -> None:
    def chunks() -> Iterator[bytes]:
        yield json.dumps(_bundle()).encode()

    reply = client.post(URL, content=chunks(), headers={"Content-Type": "application/json"})
    assert reply.status_code == 411 and reply.json()["error"] == "invalid_package"
    assert _count(db, ReviewSession) == 0


def test_an_error_after_the_create_leaves_no_draft(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def broken(**_: Any) -> None:
        raise RuntimeError("lock wait")

    monkeypatch.setattr(_quick_setup, "_run_quick_setup_contents", broken)
    with pytest.raises(RuntimeError):
        _post(client, _bundle())
    assert _count(db, ReviewSession) == 0
    assert _count(db, Reviewer) == 0


def test_a_lapsed_directory_sign_in_is_named_not_blamed_on_a_file(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def stopped(**_: Any) -> Any:
        return _quick_setup._SlotRefusal(  # pyright: ignore[reportPrivateUsage]  -- the refusal under test
            "reviewers",
            _quick_setup._SlotFailure(views.DIRECTORY_SIGN_IN),  # pyright: ignore[reportPrivateUsage]  -- as above
        )

    monkeypatch.setattr(_quick_setup, "_run_quick_setup_contents", stopped)
    reply = _post(client, _bundle())
    assert reply.status_code == 409 and reply.json()["error"] == "directory_sign_in"
    assert "slot" not in reply.json()
    assert _count(db, ReviewSession) == 0


def test_a_replay_after_an_unanswered_create_finds_the_session(
    client: TestClient, db: Session
) -> None:
    """The transfer is recorded with the draft, before the rosters, so a
    sender that lost the answer gets the same session back."""
    bundle = _bundle()
    first = _post(client, bundle).json()
    event = db.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "session.handoff_created")
    ).one()
    created = db.scalars(select(AuditEvent).where(AuditEvent.event_type == "session.created")).one()
    assert event.correlation_id == created.correlation_id
    assert _post(client, bundle).json()["session_ref"] == first["session_ref"]


def test_an_unpaired_surrogate_is_refused_not_a_500(client: TestClient, db: Session) -> None:
    """Codex, `#3780`: JSON admits an escaped lone surrogate that UTF-8
    cannot encode."""
    lone = "\ud800"
    for bundle in (
        _bundle(
            files={
                "reviewers": REVIEWERS + f"Zoe,zoe@example.edu{lone}\r\n",
                "reviewees": REVIEWEES,
            }
        ),
        _bundle(session_suggestion={"name": f"Bad {lone}", "code": "POC-SURR"}),
    ):
        body = json.dumps(bundle)  # ensure_ascii writes the surrogate as \ud800
        assert "\\ud800" in body
        reply = client.post(URL, content=body, headers={"Content-Type": "application/json"})
        assert reply.status_code == 422 and reply.json()["error"] == "invalid_package", reply.text
    assert _count(db, ReviewSession) == 0
