"""The handoff create route (segment 23A, rung 2;
`guide/archive/segment_23A_interop_poc.md`): another Cordware application's
rosters become a draft session, all or nothing, and nothing else
happens."""

from __future__ import annotations

import csv
import io
import json
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime, timedelta
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
    Instrument,
    InstrumentResponseField,
    Invitation,
    Response,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionOperator,
)
from app.services import handoffs
from app.services.instruments import GROUP_KIND_SENTINEL
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


def test_an_unknown_file_key_with_a_lone_surrogate_is_refused_not_a_500(
    client: TestClient,
) -> None:
    """Codex, `#3780`: the refusal names the key, ASCII-escaped."""
    body = json.dumps(_bundle(files={"reviewers": REVIEWERS, "reviewees": REVIEWEES, "\ud800": ""}))
    reply = client.post(URL, content=body, headers={"Content-Type": "application/json"})
    assert reply.status_code == 422 and reply.json()["error"] == "invalid_package", reply.text
    assert '"\\ud800"' in reply.json()["details"][0]


def test_a_nul_character_is_refused_before_any_database_work(
    client: TestClient, db: Session
) -> None:
    """Codex, `#3780`: an escaped NUL is valid UTF-8 that Postgres text
    columns refuse; in ``source_app`` it failed after the draft committed."""
    for bundle in (
        _bundle(source_app="utilities\u0000"),
        _bundle(session_suggestion={"name": "Bad\u0000", "code": "POC-NUL"}),
        _bundle(
            files={"reviewers": REVIEWERS + "Zoe,zoe@example.edu\u0000\r\n", "reviewees": REVIEWEES}
        ),
    ):
        reply = _post(client, bundle)
        assert reply.status_code == 422 and reply.json()["error"] == "invalid_package", reply.text
        assert "NUL" in reply.json()["details"][0]
    assert _count(db, ReviewSession) == 0


def test_an_empty_roster_is_refused(client: TestClient, db: Session) -> None:
    bundle = _bundle(files={"reviewers": "ReviewerName,ReviewerEmail\r\n", "reviewees": REVIEWEES})
    reply = _post(client, bundle)
    assert reply.status_code == 422
    assert (reply.json()["error"], reply.json()["reason"]) == ("invalid_setup", "empty_roster")
    assert _count(db, ReviewSession) == 0


def test_a_replay_of_a_transfer_cut_off_before_its_rosters_deletes_nothing(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex, `#3780`: a cancelled request leaves its draft and transfer
    record but no rosters. Its retry is told so, with the draft's link,
    and nothing is deleted; the sender's next try is a new transfer."""
    bundle = _bundle()

    class CutOff(BaseException):
        """Stands for a cancellation: a BaseException, so the route's
        ``except Exception`` does not discard the draft."""

    async def cut_off(**_: Any) -> None:
        raise CutOff

    monkeypatch.setattr(_quick_setup, "_run_quick_setup_contents", cut_off)
    with pytest.raises(BaseException):  # noqa: B017 -- the test client's wrapping varies
        _post(client, bundle)
    monkeypatch.undo()
    _age_transfer(db, handoffs.IN_PROGRESS + timedelta(seconds=1))
    retry = _post(client, bundle)
    assert retry.status_code == 409 and retry.json()["error"] == "transfer_incomplete"
    assert retry.json()["session_home_url"].startswith("/operator/sessions/")
    assert _count(db, ReviewSession) == 1  # the leftover stays, for its operator
    fresh = _post(client, _bundle(session_suggestion={"name": "Again", "code": "POC-AGAIN"}))
    assert fresh.status_code == 201


def _age_transfer(db: Session, by: timedelta) -> None:
    for event in db.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "session.handoff_created")
    ).all():
        event.created_at = datetime.now(UTC) - by
    db.commit()


def test_a_replay_while_the_first_try_may_still_run_keeps_its_transfer(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex, cordware#202: a retry while the first create is still
    checking the directory or saving finds a draft with no rosters yet.
    Within ``IN_PROGRESS`` that is ``transfer_in_progress``, which the
    sender retries with the same transfer, not ``transfer_incomplete``."""
    bundle = _bundle()

    class CutOff(BaseException):
        pass

    async def cut_off(**_: Any) -> None:
        raise CutOff

    monkeypatch.setattr(_quick_setup, "_run_quick_setup_contents", cut_off)
    with pytest.raises(BaseException):  # noqa: B017 -- the test client's wrapping varies
        _post(client, bundle)
    monkeypatch.undo()
    retry = _post(client, bundle)
    assert retry.status_code == 409 and retry.json()["error"] == "transfer_in_progress"
    assert "session_home_url" not in retry.json()
    assert _count(db, ReviewSession) == 1


def test_the_draft_and_its_transfer_record_commit_together(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex, cordware#202: a draft committed before its transfer record
    could be orphaned, its retry refused as a taken code. Neither lands
    without the other."""

    real = handoffs.audit.write_event

    def write_event(db_: Session, **kwargs: Any) -> Any:
        if kwargs.get("event_type") == handoffs.EVENT:
            raise RuntimeError("record failed")
        return real(db_, **kwargs)

    monkeypatch.setattr(handoffs.audit, "write_event", write_event)
    with pytest.raises(RuntimeError):
        _post(client, _bundle())
    db.rollback()
    assert _count(db, ReviewSession) == 0


def test_a_replay_after_the_operator_cleared_a_roster_is_still_already_created(
    client: TestClient, db: Session
) -> None:
    """Codex, `#3780`: completion is recorded, not read from what the
    rosters hold now."""
    bundle = _bundle()
    first = _post(client, bundle).json()
    for row in db.scalars(select(Reviewer)).all():
        db.delete(row)
    db.commit()
    again = _post(client, bundle)
    assert again.status_code == 200 and again.json()["status"] == "already_created"
    assert again.json()["session_ref"] == first["session_ref"]
    assert _count(db, ReviewSession) == 1


def test_a_replay_needs_the_session_now(
    client: TestClient,
    db: Session,
    make_client: Callable[[AuthenticatedUser], TestClient],
    alice: AuthenticatedUser,
) -> None:
    """Codex, `#3780`: the original sender, since removed from the
    session, gets no receipt for it."""
    bundle = _bundle()
    assert _post(client, bundle).status_code == 201
    for row in db.scalars(select(SessionOperator)).all():
        db.delete(row)
    db.commit()
    reply = _post(make_client(alice), bundle)
    assert reply.status_code == 403 and reply.json()["error"] == "not_authorized"
    assert _count(db, ReviewSession) == 1


def test_a_completed_create_records_its_completion(client: TestClient, db: Session) -> None:
    assert _post(client, _bundle()).status_code == 201
    done = db.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "session.handoff_completed")
    ).one()
    assert done.detail is not None
    assert done.detail["counts"] == {"reviewers": 2, "reviewees": 3}


def test_a_replay_cut_off_after_its_rosters_saved_completes_it(
    client: TestClient, db: Session
) -> None:
    """The rosters saved but the completion was never recorded: the
    replay records it and answers already_created."""
    bundle = _bundle()
    first = _post(client, bundle).json()
    for event in db.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "session.handoff_completed")
    ).all():
        db.delete(event)
    db.commit()
    again = _post(client, bundle)
    assert again.status_code == 200 and again.json()["session_ref"] == first["session_ref"]
    assert (
        db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(AuditEvent.event_type == "session.handoff_completed")
        )
        == 1
    )


# --- Segment 23B: the reverse flow's reads ------------------------------- #


def _status(client: TestClient, transfer_id: str) -> Any:
    return client.get(f"/operator/handoffs/{transfer_id}/status")


def test_status_reports_the_session_and_its_counts(client: TestClient, db: Session) -> None:
    bundle = _bundle()
    created = _post(client, bundle).json()
    reply = _status(client, bundle["transfer_id"])
    assert reply.status_code == 200, reply.text
    assert reply.headers["cache-control"] == "no-store"
    body = reply.json()
    assert body["status_schema_version"] == 1
    assert body["session_ref"] == created["session_ref"]
    assert body["session_home_url"] == created["session_home_url"]
    assert (body["state"], body["state_label"]) == ("draft", "Draft")
    assert body["as_of"]
    assert body["counts"] == {
        "reviewers": 2,
        "reviewees": 3,
        "instruments": 1,
        "group_instruments": 0,
        "assignments": 0,
        "assignments_completed": 0,
        "reviewers_assigned": 0,
        "reviewers_invited": 0,
        "reviewers_opened": 0,
        "reviewers_submitted": 0,
    }


def test_status_counts_assignments_of_assigned_reviewers(client: TestClient, db: Session) -> None:
    bundle = _bundle()
    _post(client, bundle)
    review_session = db.scalars(select(ReviewSession)).one()
    instrument = db.scalars(
        select(Instrument).where(Instrument.session_id == review_session.id)
    ).one()
    reviewers = db.scalars(select(Reviewer).where(Reviewer.session_id == review_session.id)).all()
    reviewees = db.scalars(select(Reviewee).where(Reviewee.session_id == review_session.id)).all()
    for reviewee in reviewees:
        db.add(
            Assignment(
                session_id=review_session.id,
                reviewer_id=reviewers[0].id,
                reviewee_id=reviewee.id,
                instrument_id=instrument.id,
            )
        )
    db.commit()
    counts = _status(client, bundle["transfer_id"]).json()["counts"]
    assert (counts["assignments"], counts["reviewers_assigned"]) == (len(reviewees), 1)


def test_status_of_an_unknown_transfer_is_not_linked(client: TestClient) -> None:
    assert _status(client, str(uuid.uuid4())).json() == {"error": "not_linked"}
    reply = _status(client, "not-a-uuid")
    assert reply.status_code == 404 and reply.json()["error"] == "not_linked"


def test_status_needs_the_session_now(
    client: TestClient,
    db: Session,
    make_client: Callable[[AuthenticatedUser], TestClient],
    bob: AuthenticatedUser,
) -> None:
    """A sender reads only a session it may operate today: another
    operator, or the creator once removed, is refused."""
    bundle = _bundle()
    _post(client, bundle)
    other = _status(make_client(bob), bundle["transfer_id"])
    assert other.status_code == 403 and other.json()["error"] == "not_authorized"


def test_status_of_an_unfinished_transfer_says_so(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    bundle = _bundle()

    class CutOff(BaseException):
        pass

    async def cut_off(**_: Any) -> None:
        raise CutOff

    monkeypatch.setattr(_quick_setup, "_run_quick_setup_contents", cut_off)
    with pytest.raises(BaseException):  # noqa: B017 -- the test client's wrapping varies
        _post(client, bundle)
    monkeypatch.undo()
    reply = _status(client, bundle["transfer_id"])
    assert reply.status_code == 409 and reply.json()["error"] == "transfer_incomplete"


def test_a_status_read_changes_nothing(client: TestClient, db: Session) -> None:
    bundle = _bundle()
    _post(client, bundle)
    before = _count(db, AuditEvent)
    for _ in range(2):
        assert _status(client, bundle["transfer_id"]).status_code == 200
    db.expire_all()
    assert _count(db, AuditEvent) == before
    assert db.scalars(select(ReviewSession)).one().status == "draft"


def _answered_session(db: Session, *, submit: bool) -> tuple[ReviewSession, list[Assignment]]:
    """The handed-off session with its first reviewer assigned every
    reviewee, and the first assignment answered (submitted or saved)."""
    review_session = db.scalars(select(ReviewSession)).one()
    sid = review_session.id
    instrument = db.scalars(select(Instrument).where(Instrument.session_id == sid)).one()
    reviewer = db.scalars(
        select(Reviewer).where(Reviewer.session_id == sid).order_by(Reviewer.id)
    ).first()
    assert reviewer is not None
    assignments = [
        Assignment(
            session_id=sid,
            reviewer_id=reviewer.id,
            reviewee_id=reviewee.id,
            instrument_id=instrument.id,
        )
        for reviewee in db.scalars(
            select(Reviewee).where(Reviewee.session_id == sid).order_by(Reviewee.id)
        )
    ]
    db.add_all(assignments)
    db.flush()
    fields = db.scalars(
        select(InstrumentResponseField).where(
            InstrumentResponseField.instrument_id == instrument.id
        )
    ).all()
    for field in fields:
        db.add(
            Response(
                assignment_id=assignments[0].id,
                response_field_id=field.id,
                value=f"=Answer {field.field_key}",
                submitted_at=datetime.now(UTC) if submit else None,
            )
        )
    db.commit()
    return review_session, assignments


def _rows(reply: Any) -> list[dict[str, str]]:
    return list(csv.DictReader(io.StringIO(reply.content.decode("utf-8"))))


def test_results_csv_carries_submitted_answers_keyed_by_application(
    client: TestClient, db: Session
) -> None:
    bundle = _bundle()
    _post(client, bundle)
    review_session, assignments = _answered_session(db, submit=True)
    reply = client.get(f"/operator/handoffs/{bundle['transfer_id']}/results.csv")
    assert reply.status_code == 200, reply.text
    assert reply.headers["content-type"].startswith("text/csv")
    assert reply.headers["cache-control"] == "no-store"
    assert reply.headers["etag"].startswith('"sha256-')
    assert reply.headers["x-review-robin-as-of"]
    rows = _rows(reply)
    assert rows and list(rows[0]) == list(handoffs.RESULTS_HEADER)
    reviewee = db.get(Reviewee, assignments[0].reviewee_id)
    assert reviewee is not None
    for row in rows:
        assert row["RevieweeEmail"] == reviewee.email_or_identifier  # the application ID
        assert row["InstrumentSeq"] == "1"
        assert row["Value"] == f"=Answer {row['FieldKey']}"  # as stored
        assert row["SubmittedAt"]
    event = db.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "session.handoff_results_exported")
    ).one()
    assert event.detail is not None
    assert event.detail["counts"] == {"rows": len(rows)}
    assert event.detail["context"]["file"] == "results.csv"


def test_results_csv_leaves_out_saved_drafts(client: TestClient, db: Session) -> None:
    bundle = _bundle()
    _post(client, bundle)
    _answered_session(db, submit=False)
    reply = client.get(f"/operator/handoffs/{bundle['transfer_id']}/results.csv")
    assert reply.status_code == 200 and _rows(reply) == []


def test_completion_csv_says_where_each_assignment_stands(client: TestClient, db: Session) -> None:
    for submit, first_state in ((False, "in_progress"), (True, "submitted")):
        bundle = _bundle(session_suggestion={"name": "S", "code": f"POC-{submit}"})
        _post(client, bundle)
        for row in db.scalars(select(Response)).all():
            db.delete(row)
        for row in db.scalars(select(Assignment)).all():
            db.delete(row)
        for row in db.scalars(select(ReviewSession)).all():
            if row.code != f"POC-{submit}":
                db.delete(row)
        db.commit()
        _answered_session(db, submit=submit)
        rows = _rows(client.get(f"/operator/handoffs/{bundle['transfer_id']}/completion.csv"))
        assert [r["State"] for r in rows] == [first_state] + ["not_started"] * (len(rows) - 1)
        assert list(rows[0]) == list(handoffs.COMPLETION_HEADER)


def test_an_unchanged_snapshot_is_not_modified_and_not_audited(
    client: TestClient, db: Session
) -> None:
    bundle = _bundle()
    _post(client, bundle)
    _answered_session(db, submit=True)
    url = f"/operator/handoffs/{bundle['transfer_id']}/results.csv"
    first = client.get(url)
    again = client.get(url)
    assert first.headers["etag"] == again.headers["etag"]  # stable over unchanged data
    before = _count(db, AuditEvent)
    same = client.get(url, headers={"If-None-Match": first.headers["etag"]})
    assert same.status_code == 304 and same.content == b""
    assert _count(db, AuditEvent) == before


def test_group_scoped_instruments_are_left_out(client: TestClient, db: Session) -> None:
    bundle = _bundle()
    _post(client, bundle)
    _answered_session(db, submit=True)
    for instrument in db.scalars(select(Instrument)).all():
        instrument.group_kind = GROUP_KIND_SENTINEL
    db.commit()
    for name in ("results.csv", "completion.csv"):
        assert _rows(client.get(f"/operator/handoffs/{bundle['transfer_id']}/{name}")) == []
    counts = _status(client, bundle["transfer_id"]).json()["counts"]
    assert counts["group_instruments"] == 1


def test_the_csvs_refuse_an_unlinked_transfer(client: TestClient) -> None:
    for name in ("results.csv", "completion.csv"):
        reply = client.get(f"/operator/handoffs/{uuid.uuid4()}/{name}")
        assert reply.status_code == 404 and reply.json()["error"] == "not_linked"
