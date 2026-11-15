"""Segment 23E rung 2: a session another application created through the
handoff carries ``linked_app`` (`guide/segment_23E_linked_sessions.md`).

The mark only: what a link turns off is rung 3's. The Utilities proof of
concept links as Apply Desk will, so the idea can be tried first.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession
from app.services import linked_apps, session_clone

from .test_handoffs import _bundle, _post, _status


def _created(client: TestClient, db: Session, **changes: Any) -> tuple[ReviewSession, str]:
    bundle = _bundle(**changes)
    reply = _post(client, bundle)
    assert reply.status_code == 201, reply.text
    return db.scalars(select(ReviewSession)).one(), bundle["transfer_id"]


def test_a_handoff_from_a_known_application_links_the_draft(
    client: TestClient, db: Session
) -> None:
    review_session, transfer = _created(client, db)  # source_app "utilities"
    assert review_session.linked_app == "utilities"
    assert _status(client, transfer).json()["linked_app"] == "utilities"
    profile = linked_apps.profile_of(review_session)
    assert profile is not None and profile.shows_results == "Utilities"


def test_an_unknown_source_app_links_nothing(client: TestClient, db: Session) -> None:
    review_session, transfer = _created(client, db, source_app="somewhere-else")
    assert review_session.linked_app is None
    assert _status(client, transfer).json()["linked_app"] is None


def test_apply_desk_has_a_profile() -> None:
    profile = linked_apps.profile_for("applydesk")
    assert profile is not None and profile.name == "Apply Desk"
    assert profile.release_off and profile.observers_off


def test_session_home_shows_the_link_and_unlink_makes_it_native(
    client: TestClient, db: Session
) -> None:
    review_session, _ = _created(client, db)
    home = f"/operator/sessions/{review_session.public_id}"
    page = client.get(home).text
    assert 'data-linked-app="utilities"' in page  # Session details' chip
    assert "Linked: Utilities</span>" in page  # the status row's pill
    assert "Session is linked with" in page
    reply = client.post(f"{home}/unlink", follow_redirects=False)
    assert reply.status_code == 303
    db.refresh(review_session)
    assert review_session.linked_app is None
    after = client.get(home).text
    assert "data-linked-app" not in after and "data-linked-pill" not in after
    event = db.scalars(select(AuditEvent).where(AuditEvent.event_type == "session.unlinked")).one()
    assert event.detail is not None and event.detail["changes"]["linked_app"] == [
        "utilities",
        None,
    ]
    # A second Unlink writes nothing.
    client.post(f"{home}/unlink", follow_redirects=False)
    assert (
        len(db.scalars(select(AuditEvent).where(AuditEvent.event_type == "session.unlinked")).all())
        == 1
    )


def test_a_copy_is_native(client: TestClient, db: Session) -> None:
    """Only the handoff links: a Duplicate never carries the mark."""
    review_session, _ = _created(client, db)
    copy = session_clone.clone_session(
        db, source=review_session, user=review_session.created_by_user, mode="all"
    )
    assert copy.linked_app is None
