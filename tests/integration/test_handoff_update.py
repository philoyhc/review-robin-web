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

from app.db.models import AuditEvent, Relationship, Reviewee, Reviewer, ReviewSession
from app.services import session_lifecycle

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
    with_settings = {"reviewers": NEW_REVIEWERS, "reviewees": REVIEWEES, "settings": SETTINGS}
    not_yet = _resend(client, created, _update_bundle(files=with_settings))
    assert not_yet.status_code == 422
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
