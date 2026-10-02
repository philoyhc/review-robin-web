"""Every outbox writer keeps the subject within its 255-character column.

``email_outbox.subject`` is ``String(255)`` and the default subjects
prefix the session name ("Invitation to review: $session_name"), so a
session name near its own 255-character limit rendered a subject
Postgres refuses (a 500; SQLite stores it). Invitation and reminder
writes now cut the subject to fit, as the responses-received queue
already does."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EmailOutbox, Invitation, ReviewSession

from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)

LONG_NAME = "n" * 255


def _ready_session(client: TestClient, db: Session) -> ReviewSession:
    client.post(
        "/operator/sessions",
        data={"name": LONG_NAME, "code": "long-subject"},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == "long-subject")
    ).scalar_one()
    client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nRae,rae@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/reviewees/import",
        files={
            "file": (
                "e.csv",
                b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n",
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, review_session.id)
    generate_via_page_button(client, review_session.id)
    client.post(
        f"/operator/sessions/{review_session.id}/workflow/prepare",
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert review_session.status == "ready"
    return review_session


def test_invitation_and_reminder_subjects_fit_for_a_255_char_name(
    client: TestClient, db: Session
) -> None:
    review_session = _ready_session(client, db)
    base = f"/operator/sessions/{review_session.id}/invitations"

    assert client.post(f"{base}/send-all", follow_redirects=False).status_code == 303
    invitation = db.execute(
        select(Invitation).where(Invitation.session_id == review_session.id)
    ).scalar_one()
    assert (
        client.post(
            f"{base}/{invitation.id}/remind", follow_redirects=False
        ).status_code
        == 303
    )

    rows = db.execute(
        select(EmailOutbox).where(EmailOutbox.session_id == review_session.id)
    ).scalars().all()
    assert {row.kind for row in rows} == {"invitation", "reminder"}
    for row in rows:
        assert len(row.subject) <= 255, row.kind
        assert row.subject.endswith("n")
