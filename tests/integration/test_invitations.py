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
    # Outbox is a dev-diagnostic surface, not a chrome tab — the only
    # entry point is the "View outbox" button on Manage Invitations.
    invitations_body = client.get(
        f"/operator/sessions/{session.id}/invitations"
    ).text
    assert (
        f'href="/operator/sessions/{session.id}/outbox">View outbox</a>'
        in invitations_body
    )
    # And no Outbox tab in the chrome (here on the Outbox page itself,
    # to confirm the nav doesn't list it anywhere).
    assert (
        f'href="/operator/sessions/{session.id}/outbox">Outbox</a>'
        not in response.text
    )


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


# --------------------------------------------------------------------------- #
# Segment 11C Part 1 — consolidated Manage Invitations page
# --------------------------------------------------------------------------- #


def test_invitations_page_renders_consolidated_column_headers(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="cols-1")
    client.post(f"/operator/sessions/{session.id}/invitations/generate")

    body = client.get(
        f"/operator/sessions/{session.id}/invitations"
    ).text
    # The full new column spec from segment_11C plan, in order.
    for header in (
        "<th>Reviewer</th>",
        "<th>Email Status</th>",
        "<th>Email Sent</th>",
        "<th>Review Progress</th>",
        "<th>Required Fields</th>",
        "<th>Last reminder</th>",
    ):
        assert header in body, f"missing column header: {header!r}"
    # The dropped "Opened" column from the pre-rewrite shape stays out.
    assert "<th>Opened</th>" not in body


def test_invitations_page_renders_review_progress_and_required_fields_format(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="prog-fmt")
    client.post(f"/operator/sessions/{session.id}/invitations/generate")

    body = client.get(
        f"/operator/sessions/{session.id}/invitations"
    ).text
    # Review Progress: "{state} ({done}/{total})". Single reviewer with
    # one assignment (Rae ⨯ Carol), no responses yet → "not started (0/1)".
    assert "not started" in body
    assert "(0/1)" in body  # review progress + required fields both 0/0 or 0/1


def test_invitations_data_cells_render_in_pills(
    client: TestClient, db: Session
) -> None:
    """Email Status / Email Sent / Review Progress / Required Fields /
    Last reminder all render their cell content inside a
    ``<span class="pill ...">`` so the table reads as a sparkline of
    state at a glance."""
    session = _ready_session(client, db, code="pill-cells")
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()

    # Pre-send state: not-sent pill, em-dash pills for empty cells.
    body = client.get(
        f"/operator/sessions/{session.id}/invitations"
    ).text
    assert '<span class="pill pill-empty">not sent</span>' in body
    # Review Progress pill (not started state) carries the formatted count.
    assert '<span class="pill pill-empty">not started (0/1)</span>' in body
    # Required Fields pill — "(0/{total})" or "—" depending on
    # whether the seeded instrument has required fields. Either way
    # the cell content is wrapped in a pill.
    assert (
        '<span class="pill pill-empty">(0/' in body
        or '<span class="pill pill-empty">—</span>' in body
    )
    # Last reminder pre-send is em-dash in pill-empty.
    assert '<span class="pill pill-empty">—</span>' in body

    # After send: Email Sent timestamp wraps in a pill-count.
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    body = client.get(
        f"/operator/sessions/{session.id}/invitations"
    ).text
    # The Email Sent cell now carries a pill-count with a timestamp
    # (look for the year prefix as a reasonable shape proxy).
    assert '<span class="pill pill-count">202' in body or \
        '<span class="pill pill-count">203' in body


def test_invitations_page_email_status_reflects_outbox_row(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="email-status")
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    body = client.get(
        f"/operator/sessions/{session.id}/invitations"
    ).text
    # Before send: no outbox row exists → "not sent" pill.
    assert "not sent" in body

    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    body = client.get(
        f"/operator/sessions/{session.id}/invitations"
    ).text
    # After send: outbox row exists at status="sent" (today the queue
    # path stamps sent immediately; Part 2 widens the value set).
    assert ">sent</span>" in body


def test_invitations_page_reviewer_name_links_to_drill_in(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="drill-link")
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    body = client.get(
        f"/operator/sessions/{session.id}/invitations"
    ).text
    assert (
        f'href="/operator/sessions/{session.id}/invitations/'
        f'{invitation.id}/detail"' in body
    )


def test_invitation_reviewer_detail_renders(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="drill-detail")
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    response = client.get(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/detail"
    )
    assert response.status_code == 200
    body = response.text
    assert "rae@example.edu" in body
    # Drill-in shows Email Status + Email Sent + Last reminder block.
    assert "Email Status" in body
    # Pre-send: no invitation URL.
    assert "No invitation URL has been issued yet." in body

    # After send: URL surfaces.
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    body = client.get(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/detail"
    ).text
    assert "/reviewer/invite/" in body


def test_per_row_remind_redirects_to_invitations_page(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="remind-redir")
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    response = client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/remind",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/operator/sessions/{session.id}/invitations"
    )


def test_invitations_remind_incomplete_bulk_endpoint(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="bulk-remind")
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    response = client.post(
        f"/operator/sessions/{session.id}/invitations/remind-incomplete",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/operator/sessions/{session.id}/invitations"
    )
    # A reminder outbox row was written.
    reminder_count = len(
        db.execute(
            select(EmailOutbox).where(
                EmailOutbox.session_id == session.id,
                EmailOutbox.kind == "reminder",
            )
        ).scalars().all()
    )
    assert reminder_count == 1


def test_invitations_remind_incomplete_409_while_session_draft(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, "bulk-draft")
    response = client.post(
        f"/operator/sessions/{session.id}/invitations/remind-incomplete",
        follow_redirects=False,
    )
    assert response.status_code == 409


def test_send_invitation_populates_cc_bcc_from_override_json(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="cc-bcc")
    # Operator sets CC + BCC on the session's email_template_overrides
    # (the editor surface from Segment 11E PR 2 writes this same shape).
    session.email_template_overrides = {
        "invitation_cc": "ops@example.edu",
        "invitation_bcc": "audit@example.edu, archive@example.edu",
    }
    db.commit()

    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )

    outbox = db.execute(
        select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)
    ).scalar_one()
    assert outbox.cc_emails == "ops@example.edu"
    assert outbox.bcc_emails == "audit@example.edu, archive@example.edu"


def test_send_reminder_populates_cc_bcc_from_override_json(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="rem-cc-bcc")
    session.email_template_overrides = {
        "reminder_cc": "ops@example.edu",
        "reminder_bcc": "archive@example.edu",
    }
    db.commit()

    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/remind"
    )

    reminder = db.execute(
        select(EmailOutbox).where(
            EmailOutbox.invitation_id == invitation.id,
            EmailOutbox.kind == "reminder",
        )
    ).scalar_one()
    assert reminder.cc_emails == "ops@example.edu"
    assert reminder.bcc_emails == "archive@example.edu"


def test_send_omits_cc_bcc_when_overrides_blank(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="cc-bcc-blank")
    # No overrides set at all.
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation.id}/send"
    )
    outbox = db.execute(
        select(EmailOutbox).where(EmailOutbox.invitation_id == invitation.id)
    ).scalar_one()
    assert outbox.cc_emails is None
    assert outbox.bcc_emails is None


# --------------------------------------------------------------------------- #
# Filter strip — status + search (Segment 11C Part 1 follow-up)
# --------------------------------------------------------------------------- #


def _ready_session_with_two_reviewers(
    client: TestClient, db: Session, code: str
) -> ReviewSession:
    """Helper: ready session with two reviewers (rae + ren) so we can
    exercise filters that narrow to one row."""
    session = _create_session(client, db, code)
    client.post(
        f"/operator/sessions/{session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nRae,rae@example.edu\n"
                b"Ren,ren@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{session.id}/reviewees/import",
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
        f"/operator/sessions/{session.id}/assignments/full-matrix",
        data={"exclude_self_review": ""},
        follow_redirects=False,
    )
    _activate(client, session.id)
    db.refresh(session)
    return session


def test_invitations_filter_strip_renders(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="filt-strip")
    body = client.get(f"/operator/sessions/{session.id}/invitations").text
    # Status dropdown lands with the four mapped options + All.
    assert '<option value="all"' in body
    assert '<option value="not_sent"' in body
    assert '<option value="not_started"' in body
    assert '<option value="in_progress"' in body
    assert '<option value="submitted"' in body
    # Search input renders, no Clear link when no filter active.
    assert 'name="q"' in body
    assert ">Clear</a>" not in body


def _strip_datalist(body: str) -> str:
    """Return the response body with `<datalist>` blocks removed.

    The Manage Invitations / Responses typeahead datalist legitimately
    contains every option regardless of the active filter, so
    "excluded reviewer not in body" assertions need to look at
    everything *outside* the datalist."""
    return re.sub(r"<datalist[^>]*>.*?</datalist>", "", body, flags=re.DOTALL)


def test_invitations_filter_status_narrows_rows(
    client: TestClient, db: Session
) -> None:
    session = _ready_session_with_two_reviewers(client, db, "filt-status")
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    # Send invitation for Rae only — Ren stays "not sent".
    invitation_rae = db.execute(
        select(Invitation)
        .join(Invitation.reviewer)
        .where(Invitation.session_id == session.id)
        .order_by(Invitation.id)
    ).scalars().first()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{invitation_rae.id}/send"
    )
    # Filter to "Not yet sent" → only Ren.
    body = _strip_datalist(client.get(
        f"/operator/sessions/{session.id}/invitations?status=not_sent"
    ).text)
    assert "ren@example.edu" in body
    assert "rae@example.edu" not in body
    # Clear link surfaces when filter is active.
    assert ">Clear</a>" in body
    # Showing-N-of-M counter renders.
    assert "Showing 1 of 2." in body


def test_invitations_filter_search_narrows_rows(
    client: TestClient, db: Session
) -> None:
    session = _ready_session_with_two_reviewers(client, db, "filt-search")
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    # Search by partial email.
    body = _strip_datalist(client.get(
        f"/operator/sessions/{session.id}/invitations?q=rae"
    ).text)
    assert "rae@example.edu" in body
    assert "ren@example.edu" not in body
    # Search is case-insensitive.
    body = _strip_datalist(client.get(
        f"/operator/sessions/{session.id}/invitations?q=REN"
    ).text)
    assert "ren@example.edu" in body


def test_invitations_filter_no_match_shows_empty_message(
    client: TestClient, db: Session
) -> None:
    session = _ready_session_with_two_reviewers(client, db, "filt-empty")
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    body = client.get(
        f"/operator/sessions/{session.id}/invitations?q=nobody"
    ).text
    assert "No reviewers match the current filter." in body


# --------------------------------------------------------------------------- #
# Bulk regenerate-all (Segment 11C Part 1 follow-up)
# --------------------------------------------------------------------------- #


def test_regenerate_all_rotates_every_token_and_resets_status(
    client: TestClient, db: Session
) -> None:
    session = _ready_session_with_two_reviewers(client, db, "regen-all-rot")
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    # Send Rae's invitation so its status is "sent" and we can confirm
    # regenerate-all flips it back to "pending".
    rae_invitation = db.execute(
        select(Invitation)
        .join(Invitation.reviewer)
        .where(Invitation.session_id == session.id)
        .order_by(Invitation.id)
    ).scalars().first()
    client.post(
        f"/operator/sessions/{session.id}/invitations/{rae_invitation.id}/send"
    )
    db.refresh(rae_invitation)
    rae_old_hash = rae_invitation.token_hash
    assert rae_invitation.status == "sent"

    response = client.post(
        f"/operator/sessions/{session.id}/invitations/regenerate-all",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        f"/operator/sessions/{session.id}/invitations"
    )

    rows = db.execute(
        select(Invitation).where(Invitation.session_id == session.id)
    ).scalars().all()
    assert len(rows) == 2
    for inv in rows:
        assert inv.status == "pending"
        assert inv.sent_at is None
        assert inv.opened_at is None
    db.refresh(rae_invitation)
    assert rae_invitation.token_hash != rae_old_hash


def test_regenerate_all_writes_single_batch_audit_event(
    client: TestClient, db: Session
) -> None:
    session = _ready_session_with_two_reviewers(client, db, "regen-all-audit")
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    client.post(
        f"/operator/sessions/{session.id}/invitations/regenerate-all"
    )

    audit_rows = db.execute(
        select(AuditEvent).where(
            AuditEvent.session_id == session.id,
            AuditEvent.event_type == "invitations.regenerated",
        )
    ).scalars().all()
    assert len(audit_rows) == 1
    detail = audit_rows[0].detail
    assert detail is not None
    assert detail["count"] == 2
    assert len(detail["invitation_ids"]) == 2
    assert len(detail["reviewer_ids"]) == 2


def test_regenerate_all_409_while_session_draft(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, "regen-all-draft")
    response = client.post(
        f"/operator/sessions/{session.id}/invitations/regenerate-all",
        follow_redirects=False,
    )
    assert response.status_code == 409


def test_regenerate_all_with_zero_invitations_writes_no_audit(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="regen-all-empty")
    # Don't generate invitations.
    response = client.post(
        f"/operator/sessions/{session.id}/invitations/regenerate-all",
        follow_redirects=False,
    )
    assert response.status_code == 303
    audit_rows = db.execute(
        select(AuditEvent).where(
            AuditEvent.session_id == session.id,
            AuditEvent.event_type == "invitations.regenerated",
        )
    ).scalars().all()
    assert audit_rows == []


def test_regenerate_all_button_renders_on_page(
    client: TestClient, db: Session
) -> None:
    session = _ready_session(client, db, code="regen-all-btn")
    body = client.get(
        f"/operator/sessions/{session.id}/invitations"
    ).text
    assert (
        f'action="/operator/sessions/{session.id}/invitations/regenerate-all"'
        in body
    )
    assert "Regenerate all" in body
