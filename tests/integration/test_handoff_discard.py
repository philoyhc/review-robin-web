"""A linked application discards the empty draft it set up (segment 23J
rung 3, `guide/segment_23J_linked_setup_first.md`): a gate dropped before
its rosters. Only an empty, unopened, still-linked draft goes, for the
operator who set it up; anything else is refused and nothing deleted."""

from __future__ import annotations

import json
import uuid
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession

from ._lookups import detail_of
from .test_handoff_set_up_first import _set_up
from .test_handoff_update import _count, _created, _resend, _update_bundle
from .test_handoffs import REVIEWEES, REVIEWERS


def _discard_bundle(**changes: Any) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "protocol": "cordware.csv-handoff",
        "protocol_version": 1,
        "operation": "reviewrobin.discard_draft_session",
        "source_app": "utilities",
        "transfer_id": str(uuid.uuid4()),
    }
    bundle.update(changes)
    return bundle


def _discard(client: TestClient, created: str, bundle: dict[str, Any] | None = None):
    return client.post(
        f"/operator/handoffs/{created}/discard",
        content=json.dumps(bundle or _discard_bundle()),
        headers={"Content-Type": "application/json", "Sec-Fetch-Site": "same-origin"},
    )


def test_an_empty_set_up_draft_is_discarded(client: TestClient, db: Session) -> None:
    review_session, created = _set_up(client, db)
    code = review_session.code
    reply = _discard(client, created)
    assert reply.status_code == 200, reply.text
    assert reply.json() == {"status": "discarded", "session_code": code}
    db.expire_all()
    assert _count(db, ReviewSession) == 0
    (deleted,) = db.scalars(select(AuditEvent).where(AuditEvent.event_type == "session.deleted"))
    assert deleted.session_id is None
    detail = detail_of(deleted)
    assert detail["snapshot"]["code"] == code
    assert detail["context"]["transfer_id"] == created
    assert detail["context"]["source_app"] == "utilities"


def test_a_retried_discard_is_already_discarded(client: TestClient, db: Session) -> None:
    review_session, created = _set_up(client, db)
    code = review_session.code
    assert _discard(client, created).status_code == 200
    again = _discard(client, created)
    assert again.status_code == 200
    assert again.json() == {"status": "already_discarded", "session_code": code}


def test_a_draft_with_rosters_is_not_discarded(client: TestClient, db: Session) -> None:
    _, created = _created(client, db)
    reply = _discard(client, created)
    assert reply.status_code == 409 and reply.json()["error"] == "session_not_empty"
    assert _count(db, ReviewSession) == 1


def test_a_set_up_draft_once_its_rosters_came_is_not_discarded(
    client: TestClient, db: Session
) -> None:
    _, created = _set_up(client, db)
    bundle = _update_bundle(files={"reviewers": REVIEWERS, "reviewees": REVIEWEES})
    assert _resend(client, created, bundle).status_code == 200
    reply = _discard(client, created)
    assert reply.status_code == 409 and reply.json()["error"] == "session_not_empty"
    assert _count(db, ReviewSession) == 1


def test_an_opened_session_is_not_discarded(client: TestClient, db: Session) -> None:
    review_session, created = _set_up(client, db)
    review_session.status = "ready"
    db.commit()
    reply = _discard(client, created)
    assert reply.status_code == 409 and reply.json()["error"] == "session_opened"
    assert _count(db, ReviewSession) == 1


def test_an_unlinked_draft_is_not_discarded(client: TestClient, db: Session) -> None:
    review_session, created = _set_up(client, db)
    review_session.linked_app = None
    db.commit()
    reply = _discard(client, created)
    assert reply.status_code == 404 and reply.json()["error"] == "not_linked"
    assert _count(db, ReviewSession) == 1


def test_another_applications_discard_is_not_linked(client: TestClient, db: Session) -> None:
    _, created = _set_up(client, db)
    reply = _discard(client, created, _discard_bundle(source_app="applydesk"))
    assert reply.status_code == 404 and reply.json()["error"] == "not_linked"
    assert _count(db, ReviewSession) == 1


def test_another_operators_draft_is_not_theirs_to_discard(client: TestClient, db: Session) -> None:
    """The transfer is recorded as another operator's: only the one who
    set the draft up may discard it."""
    from app.db.models import User

    _, created = _set_up(client, db)
    other = User(email="other@example.edu", display_name="Other")
    db.add(other)
    db.flush()
    for event in db.scalars(select(AuditEvent).where(AuditEvent.session_id.is_not(None))):
        event.actor_user_id = other.id
    db.commit()
    reply = _discard(client, created)
    assert reply.status_code == 403 and reply.json()["error"] == "not_authorized"
    assert _count(db, ReviewSession) == 1


def test_an_unknown_transfer_is_not_linked(client: TestClient, db: Session) -> None:
    assert _discard(client, str(uuid.uuid4())).json()["error"] == "not_linked"
    assert _discard(client, "not-a-uuid").json()["error"] == "not_linked"


def test_the_envelope_is_the_discard_operations(client: TestClient, db: Session) -> None:
    _, created = _set_up(client, db)
    bundle = _discard_bundle(operation="reviewrobin.update_draft_session")
    reply = _discard(client, created, bundle)
    assert reply.status_code == 422 and reply.json()["error"] == "unsupported_version"
    assert _count(db, ReviewSession) == 1


def test_a_create_retried_after_its_discard_makes_no_draft(client: TestClient, db: Session) -> None:
    """The cumulative read: a set-up whose reply was lost, discarded, then
    retried, would make a fresh draft for a gate already dropped."""
    from utilityapps.interop_poc import mock

    from .test_handoffs import _bundle, _post

    bundle = _bundle(files={"settings": mock.settings_csv()})
    assert _post(client, bundle).status_code == 201
    assert _discard(client, bundle["transfer_id"]).status_code == 200
    again = _post(client, bundle)
    assert again.status_code == 409 and again.json()["error"] == "session_discarded"
    assert _count(db, ReviewSession) == 0


def test_a_set_up_still_running_is_not_discarded(client: TestClient, db: Session) -> None:
    """The cumulative read: a discard landing between the create's record
    and its completion would leave the create to finish on nothing."""
    from app.services import handoffs

    _, created = _set_up(client, db)
    for event in db.scalars(select(AuditEvent).where(AuditEvent.event_type == handoffs.COMPLETED)):
        db.delete(event)
    db.commit()
    reply = _discard(client, created)
    assert reply.status_code == 409 and reply.json()["error"] == "transfer_in_progress"
    assert _count(db, ReviewSession) == 1


def test_a_retried_discard_from_another_application_is_not_linked(
    client: TestClient, db: Session
) -> None:
    _, created = _set_up(client, db)
    assert _discard(client, created).status_code == 200
    reply = _discard(client, created, _discard_bundle(source_app="applydesk"))
    assert reply.status_code == 404 and reply.json()["error"] == "not_linked"
