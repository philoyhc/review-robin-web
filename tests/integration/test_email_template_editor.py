"""Editor tests for ``/operator/sessions/{id}/setupinvite``
(Segment 11E PR 2).

Covers:
- GET renders the two-card layout for both invitation and reminder
  templates via ``?template=invitation`` (default) / ``?template=reminder``.
- Save persists per-template overrides into
  ``ReviewSession.email_template_overrides``; emits
  ``email_template.updated`` audit with the per-key diff.
- Empty submission for a field removes the override (falls through
  to the default at render time).
- Per-field "Reset to default" form removes a single key + emits
  ``email_template.reset`` audit.
- Unknown ``template`` value returns 404.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, ReviewSession


def _make_session(
    client: TestClient, db: Session, *, code: str = "tpl-test"
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


# ── GET ──────────────────────────────────────────────────────────────────


def test_get_default_template_is_invitation(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    body = client.get(
        f"/operator/sessions/{review_session.id}/setupinvite"
    ).text
    assert "Invitation email" in body
    # The other template is reachable as a Secondary tab.
    assert (
        f'href="/operator/sessions/{review_session.id}/setupinvite?template=reminder"'
        in body
    )


def test_get_with_reminder_template_renders_reminder(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    body = client.get(
        f"/operator/sessions/{review_session.id}/setupinvite?template=reminder"
    ).text
    assert "Reminder email" in body
    assert (
        f'href="/operator/sessions/{review_session.id}/setupinvite?template=invitation"'
        in body
    )


def test_get_with_unknown_template_404s(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    response = client.get(
        f"/operator/sessions/{review_session.id}/setupinvite?template=garbage"
    )
    assert response.status_code == 404


# ── Save ─────────────────────────────────────────────────────────────────


def test_save_persists_overrides_and_audits(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    response = client.post(
        f"/operator/sessions/{review_session.id}/setupinvite",
        data={
            "template": "invitation",
            "subject": "Custom: $session_name",
            "body": "Hi $reviewer_name — please review $session_name.",
            "cc": "ops@example.edu",
            "bcc": "",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        "/setupinvite?template=invitation"
    )

    db.refresh(review_session)
    overrides = review_session.email_template_overrides or {}
    assert overrides["invitation_subject"] == "Custom: $session_name"
    assert overrides["invitation_body"].startswith("Hi $reviewer_name")
    assert overrides["invitation_cc"] == "ops@example.edu"
    # Empty submission for bcc deliberately doesn't persist a key.
    assert "invitation_bcc" not in overrides

    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "email_template.updated")
    ).scalar_one()
    assert event.detail["template"] == "invitation"
    changes = event.detail["changes"]
    assert "invitation_subject" in changes
    assert changes["invitation_subject"][0] is None
    assert changes["invitation_subject"][1] == "Custom: $session_name"


def test_save_does_not_audit_when_nothing_changed(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    # Empty submission == no overrides; second submission == still no
    # overrides; the second save is a no-op and emits no audit event.
    client.post(
        f"/operator/sessions/{review_session.id}/setupinvite",
        data={"template": "invitation", "subject": "", "body": "", "cc": "", "bcc": ""},
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/setupinvite",
        data={"template": "invitation", "subject": "", "body": "", "cc": "", "bcc": ""},
        follow_redirects=False,
    )
    events = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "email_template.updated")
    ).scalars().all()
    assert events == []


def test_save_clearing_a_field_removes_override(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    # First save: set the subject.
    client.post(
        f"/operator/sessions/{review_session.id}/setupinvite",
        data={
            "template": "invitation",
            "subject": "First override",
            "body": "",
            "cc": "",
            "bcc": "",
        },
        follow_redirects=False,
    )
    # Second save: subject blank -> override removed.
    client.post(
        f"/operator/sessions/{review_session.id}/setupinvite",
        data={"template": "invitation", "subject": "", "body": "", "cc": "", "bcc": ""},
        follow_redirects=False,
    )
    db.refresh(review_session)
    overrides = review_session.email_template_overrides or {}
    assert "invitation_subject" not in overrides


def test_save_unknown_template_404s(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    response = client.post(
        f"/operator/sessions/{review_session.id}/setupinvite",
        data={"template": "garbage", "subject": "x"},
        follow_redirects=False,
    )
    assert response.status_code == 404


# ── Reset ────────────────────────────────────────────────────────────────


def test_reset_removes_override_and_audits(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    # Set overrides for two fields on invitation.
    client.post(
        f"/operator/sessions/{review_session.id}/setupinvite",
        data={
            "template": "invitation",
            "subject": "Custom subject",
            "body": "Custom body",
            "cc": "",
            "bcc": "",
        },
        follow_redirects=False,
    )
    # Reset only the subject.
    response = client.post(
        f"/operator/sessions/{review_session.id}/setupinvite/reset",
        data={"template": "invitation", "field": "subject"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"].endswith(
        "/setupinvite?template=invitation"
    )

    db.refresh(review_session)
    overrides = review_session.email_template_overrides or {}
    assert "invitation_subject" not in overrides
    # Body override survives.
    assert overrides["invitation_body"] == "Custom body"

    event = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "email_template.reset")
    ).scalar_one()
    assert event.detail["template"] == "invitation"
    assert event.detail["field"] == "subject"


def test_reset_unknown_field_404s(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    response = client.post(
        f"/operator/sessions/{review_session.id}/setupinvite/reset",
        data={"template": "invitation", "field": "no-such-field"},
        follow_redirects=False,
    )
    assert response.status_code == 404


# ── Per-field reset link visibility ──────────────────────────────────────


def test_reset_link_only_renders_for_overridden_fields(
    client: TestClient, db: Session
) -> None:
    review_session = _make_session(client, db)
    # Pre-save state: no overrides — no reset links anywhere.
    body = client.get(
        f"/operator/sessions/{review_session.id}/setupinvite"
    ).text
    assert "Reset subject to default" not in body

    # Override only the subject.
    client.post(
        f"/operator/sessions/{review_session.id}/setupinvite",
        data={
            "template": "invitation",
            "subject": "x",
            "body": "",
            "cc": "",
            "bcc": "",
        },
        follow_redirects=False,
    )
    body = client.get(
        f"/operator/sessions/{review_session.id}/setupinvite"
    ).text
    assert "Reset subject to default" in body
    assert "Reset body to default" not in body
