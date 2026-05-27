"""Reviewer "Recall my submission" — return-to-form path from the
summary page when the session is still ``ready``.

The summary view is gated on every assignment being submitted.
When the operator hasn't closed / reverted the session yet, the
reviewer may want to edit their submission — the Recall button
on the summary page nulls ``submitted_at`` on every response row
for the reviewer and 303s them back to the form. Recall is
forbidden in other lifecycle states (``draft`` is never reachable
from the summary, ``expired`` has no live form to return to).
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.db.models import (
    Assignment,
    AuditEvent,
    Response,
    ReviewSession,
)
from app.main import app
from app.services import session_lifecycle as lifecycle
from app.web.deps import get_current_user

from ._full_matrix import (
    generate_via_page_button,
    pin_full_matrix_on_all_instruments,
)


def _restore_operator_identity(operator: AuthenticatedUser) -> None:
    app.dependency_overrides[get_current_user] = lambda: operator


@pytest.fixture
def rae() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="rae-oid",
        email="rae@example.edu",
        name="Rae Reviewer",
        provider="aad",
    )


def _seed_session_with_rae_and_one_reviewee(
    operator_client: TestClient,
    db: Session,
    *,
    code: str,
    reviewer_email: str,
) -> ReviewSession:
    operator_client.post(
        "/operator/sessions",
        data={"name": code.title(), "code": code},
        follow_redirects=False,
    )
    review_session = db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()
    operator_client.post(
        f"/operator/sessions/{review_session.id}/reviewers/import",
        files={
            "file": (
                "r.csv",
                f"ReviewerName,ReviewerEmail\nRae,{reviewer_email}\n".encode(),
                "text/csv",
            )
        },
        follow_redirects=False,
    )
    operator_client.post(
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
    generate_via_page_button(operator_client, review_session.id)
    return review_session


def _activate(operator_client: TestClient, review_session: ReviewSession) -> None:
    operator_client.post(
        f"/operator/sessions/{review_session.id}/workflow/prepare",
        follow_redirects=False,
    )
    operator_client.post(
        f"/operator/sessions/{review_session.id}/workflow/activate",
        follow_redirects=False,
    )


def _submit(
    rae_client: TestClient, review_session: ReviewSession, db: Session
) -> None:
    assignment_ids = [
        a.id
        for a in db.execute(
            select(Assignment).where(
                Assignment.session_id == review_session.id
            )
        ).scalars()
    ]
    data: dict[str, str] = {}
    for aid in assignment_ids:
        data[f"response[{aid}][rating]"] = "5"
        data[f"response[{aid}][comments]"] = "fine"
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/1/save",
        data=data,
        follow_redirects=False,
    )
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/submit",
        follow_redirects=False,
    )


def test_recall_button_renders_on_summary_when_session_is_ready(
    client: TestClient,
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """While the session is ``ready`` the summary page carries a
    ``Recall my submission`` button posting to
    ``/reviewer/sessions/{id}/recall``."""
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="recall-button", reviewer_email=rae.email
    )
    _activate(client, review_session)
    rae_client = make_client(rae)
    _submit(rae_client, review_session, db)

    app.dependency_overrides[get_current_user] = lambda: rae
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary"
    ).text
    assert "Recall my submission" in body
    assert (
        f'action="/reviewer/sessions/{review_session.id}/recall"' in body
    )


def test_recall_button_hidden_on_summary_when_session_is_expired(
    client: TestClient,
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """Once the session is closed (``expired``) the recall button
    disappears — there's no live form to land on."""
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="recall-no-expired", reviewer_email=rae.email
    )
    _activate(client, review_session)
    rae_client = make_client(rae)
    _submit(rae_client, review_session, db)

    _restore_operator_identity(alice)
    client.post(
        f"/operator/sessions/{review_session.id}/workflow/close",
        follow_redirects=False,
    )
    db.refresh(review_session)
    assert lifecycle.is_expired(review_session)

    app.dependency_overrides[get_current_user] = lambda: rae
    body = rae_client.get(
        f"/reviewer/sessions/{review_session.id}/summary"
    ).text
    assert "Recall my submission" not in body


def test_recall_post_nulls_submitted_at_and_lands_on_form(
    client: TestClient,
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """POST ``/recall`` nulls ``submitted_at`` on every Response
    row for the reviewer and 303s to ``/1`` so the reviewer
    lands on the editable form. Audit ``responses.recalled`` is
    written; saved values are preserved (rows survive)."""
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="recall-post", reviewer_email=rae.email
    )
    _activate(client, review_session)
    rae_client = make_client(rae)
    _submit(rae_client, review_session, db)

    # Pre-condition: every response carries submitted_at.
    submitted_before = list(
        db.execute(
            select(Response)
            .join(Assignment, Assignment.id == Response.assignment_id)
            .where(Assignment.session_id == review_session.id)
        ).scalars()
    )
    assert submitted_before
    assert all(r.submitted_at is not None for r in submitted_before)

    app.dependency_overrides[get_current_user] = lambda: rae
    resp = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/recall",
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == (
        f"/reviewer/sessions/{review_session.id}/1"
    )

    # Same rows, ``submitted_at`` now None; values intact.
    db.expire_all()
    after = list(
        db.execute(
            select(Response)
            .join(Assignment, Assignment.id == Response.assignment_id)
            .where(Assignment.session_id == review_session.id)
        ).scalars()
    )
    assert len(after) == len(submitted_before)
    assert all(r.submitted_at is None for r in after)
    assert {r.value for r in after} == {r.value for r in submitted_before}

    # Audit event landed.
    events = list(
        db.execute(
            select(AuditEvent).where(
                AuditEvent.session_id == review_session.id,
                AuditEvent.event_type == "responses.recalled",
            )
        ).scalars()
    )
    assert len(events) == 1
    assert events[0].detail["counts"]["recalled"] == len(after)


def test_recall_post_403s_when_session_is_expired(
    client: TestClient,
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """The route itself rejects recall once the session has been
    closed — defense in depth alongside the hidden button."""
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="recall-403-expired", reviewer_email=rae.email
    )
    _activate(client, review_session)
    rae_client = make_client(rae)
    _submit(rae_client, review_session, db)

    _restore_operator_identity(alice)
    client.post(
        f"/operator/sessions/{review_session.id}/workflow/close",
        follow_redirects=False,
    )

    app.dependency_overrides[get_current_user] = lambda: rae
    resp = rae_client.post(
        f"/reviewer/sessions/{review_session.id}/recall",
        follow_redirects=False,
    )
    assert resp.status_code == 403


def test_recall_then_resubmit_round_trips_the_submitted_at_stamp(
    client: TestClient,
    db: Session,
    alice: AuthenticatedUser,
    rae: AuthenticatedUser,
    make_client,
) -> None:
    """After recall the reviewer can edit + re-submit, landing back
    on the summary with a fresh ``submitted_at`` stamp."""
    review_session = _seed_session_with_rae_and_one_reviewee(
        client, db, code="recall-resubmit", reviewer_email=rae.email
    )
    _activate(client, review_session)
    rae_client = make_client(rae)
    _submit(rae_client, review_session, db)
    app.dependency_overrides[get_current_user] = lambda: rae
    rae_client.post(
        f"/reviewer/sessions/{review_session.id}/recall",
        follow_redirects=False,
    )

    # Re-submit (no edits — values already present).
    _submit(rae_client, review_session, db)

    db.expire_all()
    rows = list(
        db.execute(
            select(Response)
            .join(Assignment, Assignment.id == Response.assignment_id)
            .where(Assignment.session_id == review_session.id)
        ).scalars()
    )
    assert all(r.submitted_at is not None for r in rows)
