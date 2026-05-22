"""Chrome status strip — Invitations pill distinguishes four states.

Before this change the strip rendered a hardcoded ``not sent``
placeholder; operators couldn't tell at a glance whether they had
generated invitation rows yet or whether the rows existed but no
emails had gone out. The strip now reads:

- ``Not created`` — zero ``Invitation`` rows.
- ``Not sent`` — rows exist, no outbox ``sent`` row for any reviewer.
- ``Partially sent`` — at least one reviewer has a ``sent`` outbox
  row but not every reviewer with an invitation does.
- ``All sent`` — every reviewer with an invitation has a ``sent``
  outbox row.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Invitation, Reviewer, ReviewSession
from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


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


def _seed_two_reviewers(client: TestClient, db: Session, session_id: int) -> None:
    client.post(
        f"/operator/sessions/{session_id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                b"ReviewerName,ReviewerEmail\nRae,rae@example.edu\nRen,ren@example.edu\n",
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
    pin_full_matrix_on_all_instruments(db, session_id)
    generate_via_page_button(client, session_id)


def _validated(client: TestClient, db: Session, session_id: int) -> None:
    response = client.post(
        f"/operator/sessions/{session_id}/workflow/prepare",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text


def test_invitations_pill_not_created_when_no_invitation_rows(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, "chrome-inv-none")
    _seed_two_reviewers(client, db, session.id)
    _validated(client, db, session.id)

    body = client.get(f"/operator/sessions/{session.id}").text
    assert (
        '<span class="pill pill-empty">Not created</span>' in body
    ), "expected the chrome-strip Invitations pill to read 'Not created'"


def test_invitations_pill_not_sent_after_generate_before_send(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, "chrome-inv-pending")
    _seed_two_reviewers(client, db, session.id)
    _validated(client, db, session.id)
    client.post(f"/operator/sessions/{session.id}/invitations/generate")

    body = client.get(f"/operator/sessions/{session.id}").text
    assert (
        '<span class="pill pill-warning">Not sent</span>' in body
    ), "expected the chrome-strip Invitations pill to read 'Not sent'"


def test_invitations_pill_partially_sent_when_some_reviewers_sent(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, "chrome-inv-partial")
    _seed_two_reviewers(client, db, session.id)
    _validated(client, db, session.id)
    client.post(f"/operator/sessions/{session.id}/invitations/generate")

    # Send invitation for Rae only — Ren stays pending.
    rae = db.execute(
        select(Reviewer).where(
            Reviewer.session_id == session.id,
            Reviewer.email == "rae@example.edu",
        )
    ).scalar_one()
    rae_invitation = db.execute(
        select(Invitation).where(
            Invitation.session_id == session.id,
            Invitation.reviewer_id == rae.id,
        )
    ).scalar_one()
    response = client.post(
        f"/operator/sessions/{session.id}/invitations/{rae_invitation.id}/send",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    body = client.get(f"/operator/sessions/{session.id}").text
    assert (
        '<span class="pill pill-warning">Partially sent</span>' in body
    ), "expected the chrome-strip Invitations pill to read 'Partially sent'"


def test_invitations_pill_all_sent_when_every_reviewer_sent(
    client: TestClient, db: Session
) -> None:
    session = _create_session(client, db, "chrome-inv-all")
    _seed_two_reviewers(client, db, session.id)
    _validated(client, db, session.id)
    client.post(f"/operator/sessions/{session.id}/invitations/generate")
    response = client.post(
        f"/operator/sessions/{session.id}/invitations/send-all",
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text

    body = client.get(f"/operator/sessions/{session.id}").text
    assert (
        '<span class="pill pill-info">All sent</span>' in body
    ), "expected the chrome-strip Invitations pill to read 'All sent'"
