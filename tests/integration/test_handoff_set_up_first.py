"""A linked session set up before its rosters (segment 23J rung 2,
`guide/segment_23J_linked_setup_first.md`): a linked application may
create its draft without rosters, the settings and instrument only; the
draft cannot be validated until a re-send brings them. A native create
still needs both rosters."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Instrument, Reviewee, Reviewer, ReviewSession
from app.services import handoffs, validation
from app.services import session_lifecycle as lifecycle
from utilityapps.interop_poc import mock

from ._lookups import detail_of
from .test_handoff_update import _count, _resend, _update_bundle, _with
from .test_handoffs import REVIEWEES, REVIEWERS, _bundle, _post


def _set_up(client: TestClient, db: Session) -> tuple[ReviewSession, str]:
    """A linked draft made from the settings alone; its transfer id."""
    bundle = _bundle(files={"settings": mock.settings_csv()})
    reply = _post(client, bundle)
    assert reply.status_code == 201, reply.text
    assert reply.json()["status"] == "created"
    return db.scalars(select(ReviewSession)).one(), bundle["transfer_id"]


def test_a_linked_create_may_send_no_rosters(client: TestClient, db: Session) -> None:
    review_session, _ = _set_up(client, db)
    assert review_session.linked_app == "utilities"
    assert _count(db, Reviewer) == 0 and _count(db, Reviewee) == 0
    # The instrument came with the settings, set up as a linked one.
    instrument = db.scalars(select(Instrument)).one()
    assert instrument.response_fields
    created = db.scalars(select(AuditEvent).where(AuditEvent.event_type == handoffs.EVENT)).one()
    assert detail_of(created)["context"]["rosters"] is False


def test_a_create_with_its_rosters_says_so(client: TestClient, db: Session) -> None:
    assert _post(client, _bundle()).status_code == 201
    created = db.scalars(select(AuditEvent).where(AuditEvent.event_type == handoffs.EVENT)).one()
    assert detail_of(created)["context"]["rosters"] is True


def test_the_empty_draft_cannot_be_validated(client: TestClient, db: Session) -> None:
    review_session, _ = _set_up(client, db)
    report = lifecycle.build_readiness_report(validation.validate_session_setup(db, review_session))
    assert not report.can_activate
    with pytest.raises(lifecycle.LifecycleError) as refused:
        lifecycle.mark_validated(db, review_session=review_session, user=None, report=report)  # pyright: ignore[reportArgumentType]  -- refused before the user is read
    assert refused.value.code == "has_errors"


def test_a_resend_brings_the_rosters(client: TestClient, db: Session) -> None:
    _, created = _set_up(client, db)
    bundle = _update_bundle(files={"reviewers": REVIEWERS, "reviewees": REVIEWEES})
    reply = _resend(client, created, bundle)
    assert reply.status_code == 200, reply.text
    assert _count(db, Reviewer) == 2 and _count(db, Reviewee) == 3


def test_a_resend_of_the_settings_alone_applies_them(client: TestClient, db: Session) -> None:
    """Before its rosters, a re-send may carry the settings alone: they are
    checked and written under the session lock, and the transfer recorded,
    as a re-send with rosters is (the pipeline has no file to save)."""
    review_session, created = _set_up(client, db)
    typed = "field,value,data_type\r\nsession.description,Set up first,string\r\n"
    bundle = _update_bundle(files=_with(typed))
    del bundle["files"]["reviewers"], bundle["files"]["reviewees"]
    reply = _resend(client, created, bundle)
    assert reply.status_code == 200, reply.text
    db.refresh(review_session)
    assert review_session.description == "Set up first"
    assert _count(db, Reviewer) == 0
    # Recorded: the same transfer again answers already_updated.
    assert _resend(client, created, bundle).json()["status"] == "already_updated"


def test_one_roster_without_the_other_is_refused(client: TestClient, db: Session) -> None:
    reply = _post(client, _bundle(files={"reviewers": REVIEWERS}))
    assert reply.status_code == 422 and reply.json()["error"] == "invalid_package"
    assert _count(db, ReviewSession) == 0


def test_pairs_without_rosters_are_refused(client: TestClient, db: Session) -> None:
    pairs = "ReviewerEmail,RevieweeEmail\r\nada@example.edu,SCH27-0001\r\n"
    reply = _post(client, _bundle(files={"relationships": pairs}))
    assert reply.status_code == 422 and reply.json()["error"] == "invalid_package"
    assert _count(db, ReviewSession) == 0


def test_a_native_create_still_needs_its_rosters(client: TestClient, db: Session) -> None:
    bundle = _bundle(source_app="otherapp", files={"settings": mock.settings_csv()})
    reply = _post(client, bundle)
    assert reply.status_code == 422 and reply.json()["error"] == "invalid_package"
    assert _count(db, ReviewSession) == 0


def test_a_replay_of_a_completed_set_up_is_already_created(client: TestClient, db: Session) -> None:
    bundle = _bundle(files={"settings": mock.settings_csv()})
    assert _post(client, bundle).status_code == 201
    again = _post(client, bundle)
    assert again.status_code == 200 and again.json()["status"] == "already_created"
    assert _count(db, ReviewSession) == 1


def _cut_off(db: Session, *, age: timedelta) -> None:
    """The create cut off before its completion record, ``age`` ago."""
    for event in db.scalars(select(AuditEvent).where(AuditEvent.event_type == handoffs.COMPLETED)):
        db.delete(event)
    for event in db.scalars(select(AuditEvent).where(AuditEvent.event_type == handoffs.EVENT)):
        event.created_at = datetime.now(UTC) - age
    db.commit()


def test_a_replay_of_a_recent_cut_off_set_up_is_in_progress(
    client: TestClient, db: Session
) -> None:
    bundle = _bundle(files={"settings": mock.settings_csv()})
    assert _post(client, bundle).status_code == 201
    _cut_off(db, age=timedelta(seconds=1))
    again = _post(client, bundle)
    assert again.status_code == 409 and again.json()["error"] == "transfer_in_progress"


def test_a_replay_of_an_old_cut_off_set_up_is_incomplete(client: TestClient, db: Session) -> None:
    bundle = _bundle(files={"settings": mock.settings_csv()})
    assert _post(client, bundle).status_code == 201
    _cut_off(db, age=handoffs.IN_PROGRESS + timedelta(minutes=1))
    again = _post(client, bundle)
    assert again.status_code == 409 and again.json()["error"] == "transfer_incomplete"
    assert _count(db, ReviewSession) == 1  # the draft is left for its operator


def test_a_linked_roster_with_no_rows_is_still_empty(client: TestClient, db: Session) -> None:
    """Both rosters or neither: one sent with its header alone is refused
    as any empty roster is (`empty_roster`), not read as left out."""
    header = {"reviewers": "ReviewerName,ReviewerEmail\r\n", "reviewees": REVIEWEES}
    reply = _post(client, _bundle(files=header))
    assert reply.status_code == 422 and reply.json()["reason"] == "empty_roster"
    assert _count(db, ReviewSession) == 0


def test_a_settings_alone_resend_after_the_rosters_keeps_them(
    client: TestClient, db: Session
) -> None:
    """Once the rosters are there, a re-send may still carry its settings
    alone: they apply, and the rosters stay as they are."""
    review_session, created = _set_up(client, db)
    rosters = _update_bundle(files={"reviewers": REVIEWERS, "reviewees": REVIEWEES})
    assert _resend(client, created, rosters).status_code == 200
    typed = "field,value,data_type\r\nsession.description,Later,string\r\n"
    bundle = _update_bundle(files=_with(typed))
    del bundle["files"]["reviewers"], bundle["files"]["reviewees"]
    assert _resend(client, created, bundle).status_code == 200
    db.refresh(review_session)
    assert review_session.description == "Later"
    assert _count(db, Reviewer) == 2 and _count(db, Reviewee) == 3


def test_a_settings_alone_resend_to_an_opened_session_is_refused(
    client: TestClient, db: Session
) -> None:
    review_session, created = _set_up(client, db)
    review_session.status = "ready"
    db.commit()
    typed = "field,value,data_type\r\nsession.description,Too late,string\r\n"
    bundle = _update_bundle(files=_with(typed))
    del bundle["files"]["reviewers"], bundle["files"]["reviewees"]
    reply = _resend(client, created, bundle)
    assert reply.status_code == 409 and reply.json()["error"] == "session_opened"
    db.refresh(review_session)
    assert review_session.description != "Too late"
