from __future__ import annotations

import re
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    AuditEvent,
    EmailOutbox,
    Invitation,
    ReviewSession,
)


# --------------------------------------------------------------------------- #
# Fixture helpers
# --------------------------------------------------------------------------- #


def _create_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _populate(client: TestClient, session_id: int, *, reviewer_email: str) -> None:
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                f"ReviewerName,ReviewerEmail\nRae,{reviewer_email}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session_id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session_id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )


def _activate(client: TestClient, session_id: int) -> None:
    client.get(f"/operator/sessions/{session_id}?validated=1")
    response = client.post(
        f"/operator/sessions/{session_id}/activate",
        data={"acknowledge_warnings": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def _ready_session(
    client: TestClient,
    db: Session,
    code: str = "inv-1",
    reviewer_email: str = "rae@example.edu",
) -> ReviewSession:
    session = _create_session(client, db, code)
    _populate(client, session.id, reviewer_email=reviewer_email)
    _activate(client, session.id)
    db.refresh(session)
    return session


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_generate_creates_one_per_assigned_reviewer_and_is_idempotent(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="gen-1")

    first = client.post(
        f"/operator/sessions/{session.id}/invitations/generate",
        follow_redirects=False,
    )
    assert first.status_code == 303

    rows = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "pending"
    assert rows[0].token_hash  # hash stored
    assert rows[0].sent_at is None and rows[0].opened_at is None

    second = client.post(
        f"/operator/sessions/{session.id}/invitations/generate",
        follow_redirects=False,
    )
    assert second.status_code == 303
    rows_after = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalars().all()
    assert len(rows_after) == 1  # still 1, no duplicate


def test_generate_409_while_session_draft(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, "draft-1")
    _populate(client, session.id, reviewer_email="rae@example.edu")
    response = client.post(
        f"/operator/sessions/{session.id}/invitations/generate",
        follow_redirects=False,
    )
    assert response.status_code == 409


def test_send_writes_outbox_and_flips_to_sent(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="send-1")
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send",
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.refresh(invitation)
    assert invitation.status == "sent"
    assert invitation.sent_at is not None

    outbox = db.execute(
        select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)
    ).scalar_one()
    assert outbox.kind == "invitation"
    assert outbox.status == "sent"
    assert outbox.sent_at is not None
    assert outbox.to_email == "rae@example.edu"
    assert "/reviewer/invite/" in outbox.body  # raw token URL embedded


def test_send_all_writes_one_outbox_per_pending(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="sendall-1")
    client.post(f"/operator/sessions/{session.id}/invitations/generate")

    response = client.post(
        f"/operator/sessions/{session.id}/invitations/send-all",
        follow_redirects=False,
    )
    assert response.status_code == 303
    outbox_count = len(
        db.execute(
            select(EmailOutbox).where(EmailOutbox.session_id == session.id)
        ).scalars().all()
    )
    pending_count = len(
        db.execute(
            select(Invitation).where(
                Invitation.session_id == session.id,
                Invitation.status == "pending",
            )
        ).scalars().all()
    )
    assert outbox_count == 1
    assert pending_count == 0  # all flipped to sent


def test_regenerate_rotates_token_and_resets_status(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="regen-1")
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send",
        follow_redirects=False,
    )
    db.refresh(invitation)
    old_hash = invitation.token_hash
    assert invitation.status == "sent"

    response = client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/regenerate",
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(invitation)
    assert invitation.token_hash != old_hash
    assert invitation.status == "pending"
    assert invitation.sent_at is None
    assert invitation.opened_at is None


def _extract_invite_token(outbox_body: str) -> str:
    match = re.search(r"/reviewer/invite/([A-Za-z0-9_\-]+)", outbox_body)
    assert match is not None, f"could not find invite URL in: {outbox_body!r}"
    return match.group(1)


def test_token_url_with_matching_email_stamps_opened_and_redirects(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    session = _ready_session(operator, db, code="open-1")
    operator.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    outbox = db.execute(
        select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)
    ).scalar_one()
    raw_token = _extract_invite_token(outbox.body)

    rae = AuthenticatedUser(
        principal_id="rae-oid", email="rae@example.edu", name="Rae", provider="aad"
    )
    rae_client = make_client(rae)

    response = rae_client.get(f"/reviewer/invite/{raw_token}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == f"/reviewer/sessions/{session.id}"

    db.refresh(invitation)
    assert invitation.status == "opened"
    assert invitation.opened_at is not None


def test_token_url_repeat_visit_does_not_restamp(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    session = _ready_session(operator, db, code="repeat-1")
    operator.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    outbox = db.execute(
        select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)
    ).scalar_one()
    raw_token = _extract_invite_token(outbox.body)

    rae = AuthenticatedUser(
        principal_id="rae-oid", email="rae@example.edu", name="Rae", provider="aad"
    )
    rae_client = make_client(rae)
    rae_client.get(f"/reviewer/invite/{raw_token}", follow_redirects=False)
    db.refresh(invitation)
    first_opened_at = invitation.opened_at
    rae_client.get(f"/reviewer/invite/{raw_token}", follow_redirects=False)
    rae_client.get(f"/reviewer/invite/{raw_token}", follow_redirects=False)
    db.refresh(invitation)
    assert invitation.opened_at == first_opened_at


def test_token_url_with_mismatched_email_returns_403(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    session = _ready_session(operator, db, code="mismatch-1")
    operator.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    outbox = db.execute(
        select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)
    ).scalar_one()
    raw_token = _extract_invite_token(outbox.body)

    eve = AuthenticatedUser(
        principal_id="eve-oid", email="eve@example.edu", name="Eve", provider="aad"
    )
    eve_client = make_client(eve)
    response = eve_client.get(f"/reviewer/invite/{raw_token}", follow_redirects=False)
    assert response.status_code == 403
    assert "belongs to someone else" in response.text

    db.refresh(invitation)
    assert invitation.opened_at is None  # mismatch did not stamp


def test_token_url_with_unknown_token_returns_404(client: TestClient) -> None:
    response = client.get("/reviewer/invite/not-a-real-token", follow_redirects=False)
    assert response.status_code == 404


def test_revert_then_reactivate_keeps_existing_invitations_idempotent(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="reactivate-1")
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    initial_hash = invitation.token_hash

    # Revert + reactivate without touching the roster.
    client.post(
        f"/operator/sessions/{session.id}/revert",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    _activate(client, session.id)

    # Generating again is a no-op: same row, same token.
    response = client.post(
        f"/operator/sessions/{session.id}/invitations/generate",
        follow_redirects=False,
    )
    assert response.status_code == 303
    rows = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].token_hash == initial_hash


def test_outbox_view_renders_invitation_url(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="outbox-view")
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )

    response = client.get(f"/operator/sessions/{session.id}/outbox")
    assert response.status_code == 200
    assert "/reviewer/invite/" in response.text
    assert "rae@example.edu" in response.text
    # Outbox is a first-class Operations tab in the chrome (Segment 11C
    # Part 1). The tab links to the page and renders active when on it.
    assert (
        f'href="/operator/sessions/{session.id}/outbox">Outbox</a>'
        in response.text
    )
    assert "nav-tab active" in response.text


def test_audit_events_written_for_lifecycle(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="audit-inv")
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/regenerate"
    )

    events = {
        e.event_type
        for e in db.execute(
            select(AuditEvent).where(AuditEvent.session_id == session.id)
        ).scalars()
    }
    assert {"invitations.generated", "invitation.sent", "invitation.regenerated"}.issubset(
        events
    )

    generated = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "invitations.generated")
    ).scalar_one()
    assert generated.detail is not None
    assert generated.detail["count"] == 1


def test_record_open_audit_event_written(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    session = _ready_session(operator, db, code="open-audit")
    operator.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    outbox = db.execute(
        select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)
    ).scalar_one()
    raw_token = _extract_invite_token(outbox.body)

    rae = AuthenticatedUser(
        principal_id="rae-oid", email="rae@example.edu", name="Rae", provider="aad"
    )
    make_client(rae).get(f"/reviewer/invite/{raw_token}", follow_redirects=False)

    opened = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "invitation.opened")
    ).scalar_one()
    assert opened.detail is not None
    assert opened.detail["invitation_id"] == invitation.id
