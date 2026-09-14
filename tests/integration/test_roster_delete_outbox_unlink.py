"""A sent invitation must not make a roster un-replaceable (19O.3).

``email_outbox`` references ``reviewers`` and ``invitations`` with no
``ON DELETE`` and no cascade from either parent. Deleting a reviewer
cascades ``Reviewer.invitations`` (``delete-orphan``), so before 19O.3
every reviewer-delete path raised ``IntegrityError`` on
``DELETE FROM invitations`` the moment an invitation had been sent —
reaching the operator as an unhandled 500.

Each test below therefore puts a **sent** invitation in the fixture.
That is the one thing no existing test did, which is the whole
explanation for a green suite over a live 500.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EmailOutbox, Invitation, Reviewer, ReviewSession

from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)

R_CSV = b"ReviewerName,ReviewerEmail\nR1,r1@example.com\nR2,r2@example.com\n"
R2_CSV = b"ReviewerName,ReviewerEmail\nR3,r3@example.com\nR4,r4@example.com\n"
E_CSV = b"RevieweeName,RevieweeEmail\nE1,e1@example.com\nE2,e2@example.com\n"
E2_CSV = b"RevieweeName,RevieweeEmail\nE3,e3@example.com\nE4,e4@example.com\n"


def _session_with_sent_invitations(
    client: TestClient, db: Session, code: str
) -> ReviewSession:
    """Roster + generated assignments + a *sent* invitation per reviewer."""
    client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    rs = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    client.post(
        f"/operator/sessions/{rs.id}/reviewers/import",
        files={"file": ("r.csv", R_CSV, "text/csv")},
        follow_redirects=False,
    )
    client.post(
        f"/operator/sessions/{rs.id}/reviewees/import",
        files={"file": ("e.csv", E_CSV, "text/csv")},
        follow_redirects=False,
    )
    pin_full_matrix_on_all_instruments(db, rs.id)
    generate_via_page_button(client, rs.id)

    for i, reviewer in enumerate(
        db.execute(select(Reviewer).where(Reviewer.session_id == rs.id))
        .scalars()
        .all()
    ):
        invitation = Invitation(
            session_id=rs.id, reviewer_id=reviewer.id, token_hash=f"{code}-{i}"
        )
        db.add(invitation)
        db.flush()
        db.add(
            EmailOutbox(
                session_id=rs.id,
                reviewer_id=reviewer.id,
                invitation_id=invitation.id,
                kind="invitation",
                to_email=reviewer.email or "",
                subject="Invitation",
                body="Body",
                status="sent",
            )
        )
    db.commit()
    return rs


def _outbox(db: Session, session_id: int) -> list[EmailOutbox]:
    return list(
        db.execute(
            select(EmailOutbox).where(EmailOutbox.session_id == session_id)
        ).scalars()
    )


@pytest.mark.parametrize(
    "code, path, files, data",
    [
        (
            "unlnk1",
            "reviewers/import",
            {"file": ("r2.csv", R2_CSV, "text/csv")},
            {"confirm_replace": "true", "acknowledge_response_loss": "true"},
        ),
        (
            "unlnk2",
            "quick-setup/reviewers",
            {"file": ("r2.csv", R2_CSV, "text/csv")},
            {"confirm_replace": "true", "acknowledge_response_loss": "true"},
        ),
        (
            "unlnk3",
            "reviewers/delete-all",
            None,
            {"confirm": "true", "acknowledge_response_loss": "true"},
        ),
    ],
    ids=["import-replace", "quick-setup", "delete-all"],
)
def test_reviewer_delete_path_survives_a_sent_invitation(
    client, db, code, path, files, data
):
    rs = _session_with_sent_invitations(client, db, code)
    assert _outbox(db, rs.id), "precondition: outbox rows exist"

    response = client.post(
        f"/operator/sessions/{rs.id}/{path}",
        files=files,
        data=data,
        follow_redirects=False,
    )

    assert response.status_code == 303, response.status_code
    db.expire_all()
    rows = _outbox(db, rs.id)
    assert len(rows) == 2, "the email audit log survives the delete"
    for row in rows:
        assert row.reviewer_id is None
        assert row.invitation_id is None
        # `reviewer_id IS NULL` + `sent_at`/`status` intact is what
        # "sent, recipient since removed" looks like. The delivery
        # state is not overwritten to say it.
        assert row.status == "sent"
        assert row.to_email


def test_bulk_delete_survives_a_sent_invitation(client, db):
    rs = _session_with_sent_invitations(client, db, "unlnk4")
    reviewer_ids = [
        r.id
        for r in db.execute(select(Reviewer).where(Reviewer.session_id == rs.id))
        .scalars()
        .all()
    ]

    response = client.post(
        f"/operator/sessions/{rs.id}/reviewers/bulk-delete",
        data={
            "reviewer_ids": [str(i) for i in reviewer_ids],
            "confirm": "true",
            "acknowledge_response_loss": "true",
        },
        follow_redirects=False,
    )

    assert response.status_code == 303, response.status_code
    db.expire_all()
    assert not db.execute(
        select(Reviewer).where(Reviewer.session_id == rs.id)
    ).scalars().all()
    rows = _outbox(db, rs.id)
    assert len(rows) == 2
    assert all(r.reviewer_id is None and r.invitation_id is None for r in rows)


def test_reviewee_import_leaves_the_outbox_linked(client, db):
    """The control. ``email_outbox`` has no ``reviewee_id``, so a
    reviewee replacement must not touch the outbox at all — the unlink
    is gated on the model, not applied to every roster delete."""
    rs = _session_with_sent_invitations(client, db, "unlnk5")
    before = {(r.id, r.reviewer_id, r.invitation_id) for r in _outbox(db, rs.id)}

    response = client.post(
        f"/operator/sessions/{rs.id}/reviewees/import",
        files={"file": ("e2.csv", E2_CSV, "text/csv")},
        data={"confirm_replace": "true", "acknowledge_response_loss": "true"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    db.expire_all()
    assert {
        (r.id, r.reviewer_id, r.invitation_id) for r in _outbox(db, rs.id)
    } == before
