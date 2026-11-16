"""The handoff's re-send (segment 23F rung 2,
`guide/segment_23F_linked_drafts.md`): the linked application replaces an
unopened draft's rosters, naming the draft by the transfer that created it.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    Instrument,
    Relationship,
    Reviewee,
    Reviewer,
    ReviewSession,
    SessionTag,
)
from app.services import handoffs, session_lifecycle
from utilityapps.interop_poc import mock

from ._lookups import detail_of
from .test_handoffs import REVIEWEES, REVIEWERS, SETTINGS, _bundle, _post

NEW_REVIEWERS = "ReviewerName,ReviewerEmail,ReviewerTag1\r\nCal,cal@example.edu,Panel B\r\n"
PAIRS = "ReviewerEmail,RevieweeEmail\r\ncal@example.edu,SCH27-0001\r\n"


def _created(client: TestClient, db: Session, **changes: Any) -> tuple[ReviewSession, str]:
    bundle = _bundle(**changes)
    reply = _post(client, bundle)
    assert reply.status_code == 201, reply.text
    return db.scalars(select(ReviewSession)).one(), bundle["transfer_id"]


def _update_bundle(**changes: Any) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "protocol": "cordware.csv-handoff",
        "protocol_version": 1,
        "operation": "reviewrobin.update_draft_session",
        "source_app": "utilities",
        "transfer_id": str(uuid.uuid4()),
        "files": {"reviewers": NEW_REVIEWERS, "reviewees": REVIEWEES},
    }
    bundle.update(changes)
    return bundle


def _resend(client: TestClient, created: str, bundle: dict[str, Any]):
    return client.post(
        f"/operator/handoffs/{created}/update",
        content=json.dumps(bundle),
        headers={"Content-Type": "application/json", "Sec-Fetch-Site": "same-origin"},
    )


def _emails(db: Session) -> set[str]:
    return set(db.scalars(select(Reviewer.email)))


def _count(db: Session, model: Any) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_a_resend_replaces_the_rosters(client: TestClient, db: Session) -> None:
    review_session, created = _created(client, db)
    bundle = _update_bundle(
        files={"reviewers": NEW_REVIEWERS, "reviewees": REVIEWEES, "relationships": PAIRS}
    )
    reply = _resend(client, created, bundle)
    assert reply.status_code == 200, reply.text
    assert reply.json()["status"] == "updated"
    assert reply.json()["session_ref"] == review_session.public_id
    assert _emails(db) == {"cal@example.edu"}
    assert _count(db, Reviewee) == 3 and _count(db, Relationship) == 1
    event = db.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "session.handoff_updated")
    ).one()
    assert event.detail is not None
    assert event.detail["context"]["transfer_id"] == bundle["transfer_id"]
    # A repeat applies nothing more.
    again = _resend(client, created, bundle)
    assert again.status_code == 200 and again.json()["status"] == "already_updated"
    assert (
        len(
            db.scalars(
                select(AuditEvent).where(AuditEvent.event_type == "session.handoff_updated")
            ).all()
        )
        == 1
    )


def test_an_absent_relationships_file_clears_the_pairs(client: TestClient, db: Session) -> None:
    pairs = "ReviewerEmail,RevieweeEmail\r\nada@example.edu,SCH27-0001\r\n"
    _, created = _created(
        client, db, files={"reviewers": REVIEWERS, "reviewees": REVIEWEES, "relationships": pairs}
    )
    assert _count(db, Relationship) == 1
    assert _resend(client, created, _update_bundle()).status_code == 200
    assert _count(db, Relationship) == 0


def test_a_validated_draft_returns_to_draft(client: TestClient, db: Session) -> None:
    review_session, created = _created(client, db)
    review_session.status = "validated"
    db.commit()
    assert _resend(client, created, _update_bundle()).status_code == 200
    db.refresh(review_session)
    assert review_session.status == "draft"


def test_an_opened_session_is_refused(client: TestClient, db: Session) -> None:
    review_session, created = _created(client, db)
    review_session.status = "ready"
    db.commit()
    reply = _resend(client, created, _update_bundle())
    assert reply.status_code == 409 and reply.json()["error"] == "session_opened"
    assert "cal@example.edu" not in _emails(db)
    # Reverted to draft, it is unopened again (author, 2026-11-15).
    review_session.status = "draft"
    db.commit()
    assert _resend(client, created, _update_bundle()).status_code == 200


def test_an_unlinked_or_other_applications_draft_is_not_linked(
    client: TestClient, db: Session
) -> None:
    review_session, created = _created(client, db)
    other = _resend(client, created, _update_bundle(source_app="applydesk"))
    assert other.status_code == 404 and other.json()["error"] == "not_linked"
    review_session.linked_app = None
    db.commit()
    unlinked = _resend(client, created, _update_bundle())
    assert unlinked.status_code == 404 and unlinked.json()["error"] == "not_linked"
    unknown = _resend(client, str(uuid.uuid4()), _update_bundle())
    assert unknown.status_code == 404
    assert "cal@example.edu" not in _emails(db)


def test_a_refused_file_leaves_the_draft_as_it_was(client: TestClient, db: Session) -> None:
    _, created = _created(client, db)
    bad = "ReviewerName,ReviewerEmail\r\nNo Address,\r\n"
    reply = _resend(
        client, created, _update_bundle(files={"reviewers": bad, "reviewees": REVIEWEES})
    )
    assert reply.status_code == 422 and reply.json()["slot"] == "reviewers"
    assert _emails(db) == {"ada@example.edu", "ben@example.edu"}


def test_the_envelope_is_the_update_operations(client: TestClient, db: Session) -> None:
    _, created = _created(client, db)
    as_create = _resend(
        client, created, _update_bundle(operation="reviewrobin.create_draft_session")
    )
    assert as_create.status_code == 422 and as_create.json()["error"] == "unsupported_version"
    observers = "ObserverEmail,ObserverName\r\nolu@example.edu,Olu\r\n"
    files = {"reviewers": NEW_REVIEWERS, "reviewees": REVIEWEES, "observers": observers}
    refused = _resend(client, created, _update_bundle(files=files))
    assert refused.status_code == 422 and refused.json()["slot"] == "observers"
    # The create's settings carry instruments, which are not the session's.
    with_settings = {"reviewers": NEW_REVIEWERS, "reviewees": REVIEWEES, "settings": SETTINGS}
    not_owned = _resend(client, created, _update_bundle(files=with_settings))
    assert not_owned.status_code == 422 and not_owned.json()["reason"] == "not_owned"
    assert "cal@example.edu" not in _emails(db)


def test_a_draft_holding_responses_is_refused(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A session reverted to draft can hold responses; replacing its
    rosters would discard them."""
    _, created = _created(client, db)
    monkeypatch.setattr(session_lifecycle, "session_has_responses", lambda *_: True)
    reply = _resend(client, created, _update_bundle())
    assert reply.status_code == 409 and reply.json()["error"] == "session_has_responses"
    assert "cal@example.edu" not in _emails(db)


def test_an_unlink_during_the_resend_refuses_it(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The link is checked again under the save's lock (Codex on #3915): a
    draft unlinked after the first check keeps its rosters."""
    review_session, created = _created(client, db)
    real = handoffs.check_update_target
    calls: list[int] = []

    def unlink_after_first(db_: Session, session_: ReviewSession, bundle: Any) -> None:
        calls.append(1)
        if len(calls) == 2:  # the check under the lock
            session_.linked_app = None
        real(db_, session_, bundle)

    monkeypatch.setattr(handoffs, "check_update_target", unlink_after_first)
    reply = _resend(client, created, _update_bundle())
    assert reply.status_code == 404 and reply.json()["error"] == "not_linked"
    assert len(calls) == 2
    db.expire_all()
    assert _emails(db) == {"ada@example.edu", "ben@example.edu"}
    assert not db.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "session.handoff_updated")
    ).all()


def test_the_record_commits_with_the_rosters(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A record that fails takes the rosters back with it (Codex on #3915):
    no transfer applies without the record a retry reads."""
    _, created = _created(client, db)

    def broken(*_: Any) -> None:
        raise RuntimeError("record failed")

    monkeypatch.setattr(handoffs, "record_updated", broken)
    with pytest.raises(RuntimeError):
        _resend(client, created, _update_bundle())
    db.rollback()
    assert _emails(db) == {"ada@example.edu", "ben@example.edu"}


def test_a_replay_rechecks_the_operator(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, created = _created(client, db)
    bundle = _update_bundle()
    assert _resend(client, created, bundle).status_code == 200
    monkeypatch.setattr(handoffs.permissions, "user_can_view_session", lambda *_: False)
    again = _resend(client, created, bundle)
    assert again.status_code == 403 and again.json()["error"] == "not_authorized"


def test_an_overlapping_retry_applies_once(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Transfer A pauses after its first replay lookup while A completes and
    a newer B applies; A, resumed, finds its record under the lock and
    applies nothing, so B's rosters stand (Codex on #3915)."""
    _, created = _created(client, db)
    first = _update_bundle()
    newer = _update_bundle(
        files={
            "reviewers": "ReviewerName,ReviewerEmail\r\nDee,dee@example.edu\r\n",
            "reviewees": REVIEWEES,
        }
    )
    real = handoffs.prior_update
    paused: list[int] = []

    def overlap(db_: Session, user: Any, bundle: Any) -> Any:
        found = real(db_, user, bundle)
        if bundle.transfer_id == first["transfer_id"] and not paused:
            paused.append(1)
            # Meanwhile: A completes, then B.
            monkeypatch.setattr(handoffs, "prior_update", real)
            assert _resend(client, created, first).status_code == 200
            assert _resend(client, created, newer).status_code == 200
            monkeypatch.setattr(handoffs, "prior_update", overlap)
        return found

    monkeypatch.setattr(handoffs, "prior_update", overlap)
    reply = _resend(client, created, first)
    assert reply.status_code == 200 and reply.json()["status"] == "already_updated"
    db.expire_all()
    assert _emails(db) == {"dee@example.edu"}
    records = db.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "session.handoff_updated")
    ).all()
    assert len(records) == 2


# ── Rung 3: the session settings ──────────────────────────────────────

SESSION_SETTINGS = (
    "field,value,data_type\r\n"
    "session.name,Gate 2: Interviews,string\r\n"
    "session.code,GATE-2,string\r\n"
    "session.description,Second-round interviews,string\r\n"
    "session.display_timezone,Asia/Singapore,string\r\n"
    "session.help_contact,office@example.edu,string\r\n"
    "session.scheduled_activate_at,2030-03-01T09:00:00+08:00,datetime\r\n"
    "session.deadline,2030-03-08T17:00:00+08:00,datetime\r\n"
    "session_tags[1].tag,Scholarships,string\r\n"
    "session_tags[2].tag,2030,string\r\n"
)


def _with(settings: str) -> dict[str, str]:
    return {"reviewers": NEW_REVIEWERS, "reviewees": REVIEWEES, "settings": settings}


def test_a_resend_writes_the_owned_session_settings(client: TestClient, db: Session) -> None:
    files = {"reviewers": REVIEWERS, "reviewees": REVIEWEES, "settings": mock.settings_csv()}
    review_session, created = _created(client, db, files=files)
    instrument_id = db.scalars(select(Instrument.id)).one()
    reply = _resend(client, created, _update_bundle(files=_with(SESSION_SETTINGS)))
    assert reply.status_code == 200, reply.text
    db.expire_all()
    assert (review_session.name, review_session.code) == ("Gate 2: Interviews", "GATE-2")
    assert review_session.description == "Second-round interviews"
    assert review_session.display_timezone == "Asia/Singapore"
    assert review_session.help_contact == "office@example.edu"
    assert review_session.deadline is not None and review_session.deadline.day == 8
    assert sorted(db.scalars(select(SessionTag.tag))) == ["2030", "scholarships"]
    # No instrument moved: the same row, its fields untouched.
    assert db.scalars(select(Instrument.id)).one() == instrument_id
    assert reply.json()["session_code"] == "GATE-2"
    assert _emails(db) == {"cal@example.edu"}


def test_a_row_the_application_does_not_own_is_refused(client: TestClient, db: Session) -> None:
    review_session, created = _created(client, db)
    foreign = SESSION_SETTINGS + "session.invite_offsets,-P1D,string\r\n"
    reply = _resend(client, created, _update_bundle(files=_with(foreign)))
    body = reply.json()
    assert reply.status_code == 422 and (body["slot"], body["reason"]) == ("settings", "not_owned")
    assert "session.invite_offsets" in body["details"][0]
    db.expire_all()
    assert review_session.code == "POC-TEST-1" and "cal@example.edu" not in _emails(db)


def test_a_code_another_session_holds_is_a_conflict(client: TestClient, db: Session) -> None:
    review_session, created = _created(client, db)
    other = _bundle(session_suggestion={"name": "Other", "code": "GATE-2"})
    assert _post(client, other).status_code == 201
    reply = _resend(client, created, _update_bundle(files=_with(SESSION_SETTINGS)))
    assert reply.status_code == 409 and reply.json()["error"] == "session_code_conflict"
    db.expire_all()
    assert review_session.code == "POC-TEST-1"


def test_settings_the_checks_refuse_leave_the_draft_as_it_was(
    client: TestClient, db: Session
) -> None:
    review_session, created = _created(client, db)
    cases = [
        "field,value,data_type\r\nsession.display_timezone,Mars/Base,string\r\n",
        "field,value,data_type\r\nsession.deadline,not a date,datetime\r\n",
        # End before Start.
        "field,value,data_type\r\n"
        "session.scheduled_activate_at,2030-03-08T09:00:00+00:00,datetime\r\n"
        "session.deadline,2030-03-01T09:00:00+00:00,datetime\r\n",
        "field,value,data_type\r\nsession.code,,string\r\n",
    ]
    for settings in cases:
        reply = _resend(client, created, _update_bundle(files=_with(settings)))
        assert reply.status_code == 422 and reply.json()["slot"] == "settings", settings
    db.expire_all()
    assert review_session.code == "POC-TEST-1" and review_session.deadline is None
    assert "cal@example.edu" not in _emails(db)


def test_a_settings_only_change_keeps_what_the_file_leaves_out(
    client: TestClient, db: Session
) -> None:
    review_session, created = _created(client, db)
    only_name = "field,value,data_type\r\nsession.name,Renamed,string\r\n"
    files = {"reviewers": REVIEWERS, "reviewees": REVIEWEES, "settings": only_name}
    assert _resend(client, created, _update_bundle(files=files)).status_code == 200
    db.expire_all()
    assert (review_session.name, review_session.code) == ("Renamed", "POC-TEST-1")


def test_a_short_settings_row_is_refused_not_padded(client: TestClient, db: Session) -> None:
    """A truncated row is refused as the import refuses it, rather than
    read as a blank value that clears the field (Codex on #3920)."""
    review_session, created = _created(client, db)
    with_end = "field,value,data_type\r\nsession.deadline,2030-03-08T17:00:00+00:00,datetime\r\n"
    assert _resend(client, created, _update_bundle(files=_with(with_end))).status_code == 200
    short = "field,value,data_type\r\nsession.deadline\r\n"
    reply = _resend(client, created, _update_bundle(files=_with(short)))
    assert reply.status_code == 422 and reply.json()["slot"] == "settings"
    db.expire_all()
    assert review_session.deadline is not None


def test_a_schedule_moved_past_the_old_end_is_accepted(client: TestClient, db: Session) -> None:
    """The order is checked on the values the re-send writes, not the
    import's fill-blank End (Codex on #3920)."""
    review_session, created = _created(client, db)
    march = (
        "field,value,data_type\r\n"
        "session.scheduled_activate_at,2030-03-01T09:00:00+00:00,datetime\r\n"
        "session.deadline,2030-03-08T17:00:00+00:00,datetime\r\n"
    )
    assert _resend(client, created, _update_bundle(files=_with(march))).status_code == 200
    april = march.replace("2030-03-", "2030-04-")
    reply = _resend(client, created, _update_bundle(files=_with(april)))
    assert reply.status_code == 200, reply.text
    db.expire_all()
    assert review_session.deadline is not None and review_session.deadline.month == 4


def test_the_schedule_is_rechecked_under_the_lock(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An overlapping re-send that moved End since the first check is seen
    under the save's lock (Codex on #3920): a Start now after that End is
    refused, and the rosters stay as they were."""
    from datetime import UTC, datetime

    review_session, created = _created(client, db)
    march = (
        "field,value,data_type\r\n"
        "session.scheduled_activate_at,2030-03-01T09:00:00+00:00,datetime\r\n"
        "session.deadline,2030-03-08T17:00:00+00:00,datetime\r\n"
    )
    assert _resend(client, created, _update_bundle(files=_with(march))).status_code == 200
    real = handoffs.guard_update

    def end_moved_meanwhile(db_: Session, user: Any, session_: ReviewSession, bundle: Any) -> None:
        session_.deadline = datetime(2030, 3, 4, 17, tzinfo=UTC)
        db_.flush()  # as if committed by the other re-send
        real(db_, user, session_, bundle)

    monkeypatch.setattr(handoffs, "guard_update", end_moved_meanwhile)
    start_only = (
        "field,value,data_type\r\n"
        "session.scheduled_activate_at,2030-03-06T09:00:00+00:00,datetime\r\n"
    )
    files = {"reviewers": REVIEWERS, "reviewees": REVIEWEES, "settings": start_only}
    reply = _resend(client, created, _update_bundle(files=files))
    assert reply.status_code == 422, reply.text
    assert reply.json()["slot"] == "settings"
    db.expire_all()
    assert _emails(db) == {"cal@example.edu"}
    assert review_session.scheduled_activate_at is not None
    assert review_session.scheduled_activate_at.day == 1


def test_the_proof_of_concepts_re_send_updates_its_draft(client: TestClient, db: Session) -> None:
    """Segment 23F rung 4: Utilities' re-send bundle, applied to a draft its
    create made, drops a reviewer and an application and re-sends the
    session settings it owns."""
    people = mock.reviewers("Al Operator", "alice@example.edu")
    suggestion = {"name": mock.EXERCISE, "code": "POC-RESEND"}  # the page adds a code
    review_session, created = _created(
        client, db, **{**mock.bundle(people), "session_suggestion": suggestion}
    )
    bundle = {**mock.resend_bundle(people), "transfer_id": str(uuid.uuid4())}
    reply = _resend(client, created, bundle)
    assert reply.status_code == 200, reply.text
    db.expire_all()
    assert mock.RESEND_DROPS_REVIEWER not in _emails(db)
    assert mock.RESEND_DROPS_APPLICATION not in set(
        db.scalars(select(Reviewee.email_or_identifier))
    )
    assert review_session.description == "Updated by a re-send from Utilities"
    assert sorted(db.scalars(select(SessionTag.tag))) == ["2027", "applydesk"]
    # Every owned part changed as the re-send changes it (author, 2026-11-16).
    assert review_session.deadline is not None and review_session.deadline.day == 29
    instrument = db.scalars(select(Instrument)).one()
    assert (instrument.name, instrument.description) == (
        mock.RESEND_INSTRUMENT,
        mock.GATE_DESCRIPTION,
    )
    assert all("re-send" in (f.help_text or "") for f in instrument.response_fields)


#: A re-send of the gate's instrument (segment 23F rung 7b): renamed,
#: described, ``comment`` relabeled and moved first, ``score`` dropped and
#: a ``recommend`` list added.
INSTRUMENT_SETTINGS = (
    "field,value,data_type\r\n"
    "instruments[1].name,Gate 2: Interviews with the scholarship panel,string\r\n"
    "instruments[1].description,Rate each interview,string\r\n"
    "instruments[1].response_fields[1].field_key,comment,string\r\n"
    "instruments[1].response_fields[1].label,Comments,string\r\n"
    "instruments[1].response_fields[1].response_type,text,string\r\n"
    "instruments[1].response_fields[1].data_type,String,string\r\n"
    "instruments[1].response_fields[1].help_text,Two lines at most,string\r\n"
    "instruments[1].response_fields[2].field_key,recommend,string\r\n"
    "instruments[1].response_fields[2].label,Recommend?,string\r\n"
    "instruments[1].response_fields[2].response_type,list,string\r\n"
    "instruments[1].response_fields[2].data_type,List,string\r\n"
    'instruments[1].response_fields[2].list_csv,"Yes,No",string\r\n'
    "instruments[1].response_fields[2].required,true,boolean\r\n"
)


def _instrument_created(client: TestClient, db: Session) -> tuple[ReviewSession, str]:
    files = {"reviewers": REVIEWERS, "reviewees": REVIEWEES, "settings": mock.settings_csv()}
    return _created(client, db, files=files)


def test_a_resend_writes_the_instruments_owned_rows(client: TestClient, db: Session) -> None:
    _, created = _instrument_created(client, db)
    instrument = db.scalars(select(Instrument)).one()
    comment_id = next(f.id for f in instrument.response_fields if f.field_key == "comment")
    instrument.column_widths = {"rf_" + str(comment_id): 240}
    db.commit()
    reply = _resend(client, created, _update_bundle(files=_with(INSTRUMENT_SETTINGS)))
    assert reply.status_code == 200, reply.text
    db.expire_all()
    instrument = db.scalars(select(Instrument)).one()
    assert instrument.name == "Gate 2: Interviews with the scholarship panel"
    assert instrument.short_label == "Gate 2: Interviews with the scho"
    assert instrument.description == "Rate each interview"
    fields = sorted(instrument.response_fields, key=lambda f: f.order)
    assert [(f.field_key, f.label, f.required) for f in fields] == [
        ("comment", "Comments", False),
        ("recommend", "Recommend?", True),
    ]
    # Matched by key: the same row, its width kept.
    assert fields[0].id == comment_id and fields[0].help_text == "Two lines at most"
    assert instrument.column_widths == {f"rf_{comment_id}": 240}
    assert fields[1]._inline_list_csv == "Yes,No"
    saved = db.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "instrument.response_fields_saved")
    ).one()
    assert detail_of(saved)["set_changes"]["removed"] == [{"field_key": "score", "label": "Score"}]


def test_a_resend_without_field_rows_keeps_the_fields(client: TestClient, db: Session) -> None:
    _, created = _instrument_created(client, db)
    named = "field,value,data_type\r\ninstruments[1].name,Gate 3,string\r\n"
    reply = _resend(client, created, _update_bundle(files=_with(named)))
    assert reply.status_code == 200, reply.text
    db.expire_all()
    instrument = db.scalars(select(Instrument)).one()
    assert (instrument.name, instrument.short_label) == ("Gate 3", "Gate 3")
    assert {f.field_key for f in instrument.response_fields} == {"score", "comment"}


def test_a_branch_row_is_not_the_applications(client: TestClient, db: Session) -> None:
    _, created = _instrument_created(client, db)
    branched = INSTRUMENT_SETTINGS + (
        "instruments[1].response_fields[2].branch_parent,comment,string\r\n"
    )
    reply = _resend(client, created, _update_bundle(files=_with(branched)))
    body = reply.json()
    assert reply.status_code == 422 and body["reason"] == "not_owned"


def test_a_field_without_a_data_type_is_refused(client: TestClient, db: Session) -> None:
    _, created = _instrument_created(client, db)
    untyped = INSTRUMENT_SETTINGS.replace(
        "instruments[1].response_fields[2].data_type,List,string\r\n", ""
    )
    reply = _resend(client, created, _update_bundle(files=_with(untyped)))
    body = reply.json()
    assert reply.status_code == 422 and body["slot"] == "settings"
    assert "response_fields[2].data_type" in body["details"][0]
    db.expire_all()
    assert {f.field_key for f in db.scalars(select(Instrument)).one().response_fields} == {
        "score",
        "comment",
    }


def _display_sources(db: Session) -> set[tuple[str, str]]:
    instrument = db.scalars(select(Instrument)).one()
    db.refresh(instrument, ["display_fields"])
    return {(f.source_type, f.source_field) for f in instrument.display_fields}


def test_a_resend_seeds_no_display_field(client: TestClient, db: Session) -> None:
    """The display fields are the operator's from the create on: a re-send
    whose reviewees carry a tag adds no tag field back (the cold read)."""
    _, created = _instrument_created(client, db)
    before = _display_sources(db)
    assert not any(field.startswith("tag_") for _, field in before)
    reply = _resend(client, created, _update_bundle())
    assert reply.status_code == 200, reply.text
    db.expire_all()
    assert _display_sources(db) == before


def test_instrument_rows_on_a_draft_of_two_instruments_are_refused(
    client: TestClient, db: Session
) -> None:
    """Not a 500 (the cold read): the rows name ``instruments[1]`` of a
    draft that must hold one."""
    review_session, created = _instrument_created(client, db)
    db.add(Instrument(session_id=review_session.id, name="Another", order=1))
    db.commit()
    reply = _resend(client, created, _update_bundle(files=_with(INSTRUMENT_SETTINGS)))
    assert reply.status_code == 422 and reply.json()["slot"] == "settings"


def test_a_rename_is_audited(client: TestClient, db: Session) -> None:
    _, created = _instrument_created(client, db)
    reply = _resend(client, created, _update_bundle(files=_with(INSTRUMENT_SETTINGS)))
    assert reply.status_code == 200, reply.text
    renamed = db.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "instrument.renamed")
    ).one()
    assert detail_of(renamed)["changes"]["name"][1] == (
        "Gate 2: Interviews with the scholarship panel"
    )


def test_a_cleared_branch_is_audited(client: TestClient, db: Session) -> None:
    """A re-send leaves every field unbranched; a branch it clears is in the
    event, though the card's Save audits branches elsewhere (Codex on #3926)."""
    _, created = _instrument_created(client, db)
    instrument = db.scalars(select(Instrument)).one()
    fields = {f.field_key: f for f in instrument.response_fields}
    fields["comment"].branch_parent_id = fields["score"].id
    fields["score"].branch_op = "eq"
    fields["score"].branch_value = "5"
    db.commit()
    keep_both = (
        "field,value,data_type\r\n"
        "instruments[1].name,Mock review,string\r\n"
        "instruments[1].response_fields[1].field_key,score,string\r\n"
        "instruments[1].response_fields[1].label,Score,string\r\n"
        "instruments[1].response_fields[1].response_type,1-to-5int,string\r\n"
        "instruments[1].response_fields[1].data_type,Integer,string\r\n"
        "instruments[1].response_fields[1].min,1,decimal\r\n"
        "instruments[1].response_fields[1].max,5,decimal\r\n"
        "instruments[1].response_fields[1].step,1,decimal\r\n"
        "instruments[1].response_fields[2].field_key,comment,string\r\n"
        "instruments[1].response_fields[2].label,Comment,string\r\n"
        "instruments[1].response_fields[2].response_type,text,string\r\n"
        "instruments[1].response_fields[2].data_type,String,string\r\n"
    )
    reply = _resend(client, created, _update_bundle(files=_with(keep_both)))
    assert reply.status_code == 200, reply.text
    saved = db.scalars(
        select(AuditEvent).where(AuditEvent.event_type == "instrument.response_fields_saved")
    ).one()
    changed = {u["field_key"]: u["changes"] for u in detail_of(saved)["set_changes"]["updated"]}
    assert "branch_parent_id" in changed["comment"]
    assert "branch_op" in changed["score"] and "branch_value" in changed["score"]


def test_a_field_with_impossible_bounds_is_refused(client: TestClient, db: Session) -> None:
    """The card's shape rule holds for a re-sent field (Codex on #3926):
    Max under Min is refused, and the fields stay as they were."""
    _, created = _instrument_created(client, db)
    upside_down = (
        "field,value,data_type\r\n"
        "instruments[1].name,Mock review,string\r\n"
        "instruments[1].response_fields[1].field_key,score,string\r\n"
        "instruments[1].response_fields[1].label,Score,string\r\n"
        "instruments[1].response_fields[1].response_type,1-to-5int,string\r\n"
        "instruments[1].response_fields[1].data_type,Integer,string\r\n"
        "instruments[1].response_fields[1].min,5,decimal\r\n"
        "instruments[1].response_fields[1].max,1,decimal\r\n"
        "instruments[1].response_fields[1].required,true,boolean\r\n"
    )
    reply = _resend(client, created, _update_bundle(files=_with(upside_down)))
    body = reply.json()
    assert reply.status_code == 422 and body["slot"] == "settings"
    assert "Max must be at least Min" in body["details"][0]
    db.expire_all()
    score = next(
        f for f in db.scalars(select(Instrument)).one().response_fields if f.field_key == "score"
    )
    assert (score._inline_min, score._inline_max) == (1, 5)
