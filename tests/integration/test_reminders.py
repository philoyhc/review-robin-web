from __future__ import annotations

import re
from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    AuditEvent,
    EmailOutbox,
    Invitation,
    Reviewer,
    ReviewSession,
)


# --------------------------------------------------------------------------- #
# Setup helpers
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


def _populate(client: TestClient, session_id: int, *, reviewers: list[str]) -> None:
    csv = b"ReviewerName,ReviewerEmail\n" + b"".join(
        f"R{i},{email}\n".encode() for i, email in enumerate(reviewers)
    )
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={"file": ("r.csv", csv, "text/csv")},
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
    code: str,
    *,
    reviewers: list[str],
) -> ReviewSession:
    session = _create_session(client, db, code)
    _populate(client, session.id, reviewers=reviewers)
    _activate(client, session.id)
    db.refresh(session)
    return session


_INVITE_URL_RE = re.compile(r"https?://\S+/reviewer/invite/[A-Za-z0-9_\-]+")


def _extract_token(body: str) -> str:
    match = re.search(r"/reviewer/invite/([A-Za-z0-9_\-]+)", body)
    assert match is not None, body
    return match.group(1)


def _extract_url(body: str) -> str:
    match = _INVITE_URL_RE.search(body)
    assert match is not None, body
    return match.group(0)


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #


def test_monitoring_url_redirects_to_invitations(
    client: TestClient, db: Session
) -> None:
    """Segment 11C Part 1 PR 3 retired the Monitoring page; existing
    bookmarks 303 forward to ``/invitations``."""
    session = _ready_session(
        client, db, "mon-redir", reviewers=["rae@example.edu"]
    )
    response = client.get(
        f"/operator/sessions/{session.id}/monitoring",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/operator/sessions/{session.id}/invitations"
    )


def test_send_reminder_reuses_invitation_url_without_rotating_token(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(
        client, db, "rem-reuse", reviewers=["rae@example.edu"]
    )
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    invitation_outbox = db.execute(
        select(EmailOutbox).where(
            EmailOutbox.invitation_id == invitation.id,
            EmailOutbox.kind == "invitation",
        )
    ).scalar_one()
    original_url = _extract_url(invitation_outbox.body)
    db.refresh(invitation)
    original_hash = invitation.token_hash

    response = client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/remind",
        follow_redirects=False,
    )
    assert response.status_code == 303

    reminder = db.execute(
        select(EmailOutbox).where(
            EmailOutbox.invitation_id == invitation.id,
            EmailOutbox.kind == "reminder",
        )
    ).scalar_one()
    reminder_url = _extract_url(reminder.body)
    assert reminder_url == original_url
    db.refresh(invitation)
    assert invitation.token_hash == original_hash  # NOT rotated
    assert invitation.last_reminder_at is not None


def test_send_reminder_falls_back_to_fresh_send_when_never_sent(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(
        client, db, "rem-fallback", reviewers=["rae@example.edu"]
    )
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    pre_hash = invitation.token_hash

    response = client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/remind",
        follow_redirects=False,
    )
    assert response.status_code == 303

    rows = db.execute(
        select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].kind == "invitation"  # fell back to fresh send
    db.refresh(invitation)
    assert invitation.token_hash != pre_hash  # rotated
    assert invitation.status == "sent"
    assert invitation.last_reminder_at is not None


def test_remind_incomplete_targets_only_incomplete(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    session = _ready_session(
        operator,
        db,
        "rem-bulk",
        reviewers=["rae@example.edu", "sam@example.edu"],
    )
    operator.post(f"/operator/sessions/{session.id}/invitations/generate")
    rae_inv = db.execute(
        select(Invitation, Reviewer)
        .join(Reviewer, Reviewer.id == Invitation.reviewer_id)
        .where(Reviewer.email == "rae@example.edu")
    ).one()[0]
    sam_inv = db.execute(
        select(Invitation, Reviewer)
        .join(Reviewer, Reviewer.id == Invitation.reviewer_id)
        .where(Reviewer.email == "sam@example.edu")
    ).one()[0]
    operator.post(
        f"/operator/sessions/{session.id}/invitations/{rae_inv.id}/send"
    )
    operator.post(
        f"/operator/sessions/{session.id}/invitations/{sam_inv.id}/send"
    )

    # Rae submits in full so she's "submitted" and excluded from reminders.
    rae_assignment = db.execute(
        select(Assignment, Reviewer)
        .join(Reviewer, Reviewer.id == Assignment.reviewer_id)
        .where(Reviewer.email == "rae@example.edu")
    ).one()[0]
    rae = AuthenticatedUser(
        principal_id="r", email="rae@example.edu", name="Rae", provider="aad"
    )
    rae_client = make_client(rae)
    rae_client.post(
        f"/reviewer/sessions/{session.id}/submit",
        data={f"response[{rae_assignment.id}][rating]": "5"},
        follow_redirects=False,
    )

    operator2 = make_client(alice)
    response = operator2.post(
        f"/operator/sessions/{session.id}/invitations/remind-incomplete",
        follow_redirects=False,
    )
    assert response.status_code == 303

    # Sam (incomplete) got a reminder. Rae (submitted) did not.
    sam_reminders = db.execute(
        select(EmailOutbox).where(
            EmailOutbox.invitation_id == sam_inv.id,
            EmailOutbox.kind == "reminder",
        )
    ).scalars().all()
    rae_reminders = db.execute(
        select(EmailOutbox).where(
            EmailOutbox.invitation_id == rae_inv.id,
            EmailOutbox.kind == "reminder",
        )
    ).scalars().all()
    assert len(sam_reminders) == 1
    assert len(rae_reminders) == 0


def test_remind_incomplete_writes_single_batch_audit_event(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(
        client, db, "rem-audit", reviewers=["rae@example.edu", "sam@example.edu"]
    )
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitations_rows = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalars().all()
    for inv in invitations_rows:
        client.post(
            f"/operator/sessions/{session.id}/invitations/{inv.id}/send"
        )

    client.post(
        f"/operator/sessions/{session.id}/invitations/remind-incomplete",
        follow_redirects=False,
    )

    events = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "reminders.sent",
            AuditEvent.session_id == session.id,
        )
    ).scalars().all()
    assert len(events) == 1
    assert events[0].detail is not None
    assert events[0].detail["count"] == 2


def test_per_row_and_bulk_reminders_stamp_last_reminder_at(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(
        client, db, "rem-stamp", reviewers=["rae@example.edu"]
    )
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )

    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/remind",
        follow_redirects=False,
    )
    db.refresh(invitation)
    first = invitation.last_reminder_at
    assert first is not None

    client.post(
        f"/operator/sessions/{session.id}/invitations/remind-incomplete",
        follow_redirects=False,
    )
    db.refresh(invitation)
    assert invitation.last_reminder_at is not None
    assert invitation.last_reminder_at >= first


def test_reminder_actions_409_while_session_draft(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, "draft-rem")
    _populate(client, session.id, reviewers=["rae@example.edu"])
    # Cannot generate invitations on a draft session, so we fabricate one
    # directly to simulate stale state and exercise the gating.
    reviewer = db.execute(
        select(Reviewer).where(Reviewer.session_id == session.id)
    ).scalar_one()
    invitation = Invitation(
        session_id=session.id,
        reviewer_id=reviewer.id,
        token_hash="placeholder",
        status="sent",
    )
    db.add(invitation)
    db.commit()

    bulk = client.post(
        f"/operator/sessions/{session.id}/invitations/remind-incomplete",
        follow_redirects=False,
    )
    assert bulk.status_code == 409

    single = client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/remind",
        follow_redirects=False,
    )
    assert single.status_code == 409


def test_submitted_with_warn_override_classified_incomplete(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    session = _ready_session(
        operator, db, "rem-override", reviewers=["rae@example.edu"]
    )
    operator.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )

    # Rae attempts a submit with the required ``rating`` left blank.
    # Submit blocks (no acknowledge-and-override path), but the
    # ``comments`` draft commits — Rae still ends up classified as
    # incomplete by the monitoring path.
    rae = AuthenticatedUser(
        principal_id="r", email="rae@example.edu", name="Rae", provider="aad"
    )
    rae_client = make_client(rae)
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == session.id)
    ).scalar_one()
    rae_client.post(
        f"/reviewer/sessions/{session.id}/submit",
        data={
            f"response[{assignment.id}][comments]": "fine",
        },
        follow_redirects=False,
    )

    operator2 = make_client(alice)
    response = operator2.post(
        f"/operator/sessions/{session.id}/invitations/remind-incomplete",
        follow_redirects=False,
    )
    assert response.status_code == 303
    reminders = db.execute(
        select(EmailOutbox).where(
            EmailOutbox.invitation_id == invitation.id,
            EmailOutbox.kind == "reminder",
        )
    ).scalars().all()
    assert len(reminders) == 1


def test_remind_incomplete_writes_no_audit_when_zero_targets(
    db: Session,
    alice: AuthenticatedUser,
    make_client: Callable[[AuthenticatedUser], TestClient],
) -> None:
    operator = make_client(alice)
    session = _ready_session(
        operator, db, "rem-empty", reviewers=["rae@example.edu"]
    )
    operator.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    operator.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )

    rae = AuthenticatedUser(
        principal_id="r", email="rae@example.edu", name="Rae", provider="aad"
    )
    rae_client = make_client(rae)
    assignment = db.execute(
        select(Assignment).where(Assignment.session_id == session.id)
    ).scalar_one()
    rae_client.post(
        f"/reviewer/sessions/{session.id}/submit",
        data={f"response[{assignment.id}][rating]": "5"},
        follow_redirects=False,
    )

    operator2 = make_client(alice)
    operator2.post(
        f"/operator/sessions/{session.id}/invitations/remind-incomplete",
        follow_redirects=False,
    )
    events = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "reminders.sent",
            AuditEvent.session_id == session.id,
        )
    ).scalars().all()
    reminders = db.execute(
        select(EmailOutbox).where(
            EmailOutbox.session_id == session.id,
            EmailOutbox.kind == "reminder",
        )
    ).scalars().all()
    assert events == []
    assert reminders == []
