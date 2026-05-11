"""Coverage for Segment 16B PR 2 — per-session owner management.

Exercises the new Owners section on
``/operator/sessions/{id}/edit``:

- Owner can add another workspace operator as a co-owner.
- Owner can remove a non-self owner.
- Owner can self-remove when another owner exists.
- Last-owner remove → 409.
- Add target not on the workspace allowlist → 303 with
  ``owners_error=not_in_workspace``.
- Add target already an owner → 303 with
  ``owners_error=already_owner``.
- Sys-admin who isn't on session_operators can hit GET /edit (the
  relaxed gate) and self-add as owner — then has full operator
  access via the normal session-operator path.
- Audit events emitted with correct envelope.
- Plain non-owner operator still 403s on /edit.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditEvent, ReviewSession, SessionOperator, User


def _make_session(
    client: TestClient, db: Session, *, code: str
) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": "Spring", "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def _seed_user(
    db: Session,
    *,
    email: str,
    is_operator: bool = True,
    is_sys_admin: bool = False,
) -> User:
    user = User(
        email=email,
        is_operator=is_operator,
        is_sys_admin=is_sys_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


# --- Render -----------------------------------------------------------------


def test_edit_page_renders_owners_section_for_owner(
    db: Session,
    client: TestClient,
) -> None:
    review_session = _make_session(client, db, code="own-1")
    response = client.get(f"/operator/sessions/{review_session.id}/edit")
    assert response.status_code == 200
    # Owners card present; creator (alice) is the single owner.
    assert 'id="owners"' in response.text
    assert "alice@example.edu" in response.text


def test_edit_page_403s_for_plain_non_member_operator(
    db: Session,
    client: TestClient,
    make_client,
    bob,
) -> None:
    review_session = _make_session(client, db, code="own-403")
    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sessions/{review_session.id}/edit",
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_edit_page_renders_for_sys_admin_non_member(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sys-admin Bob isn't a session_operator on alice's session
    but reaches /edit via the relaxed gate."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="own-sa")

    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sessions/{review_session.id}/edit"
    )
    assert response.status_code == 200
    assert 'id="owners"' in response.text


# --- Add owner --------------------------------------------------------------


def test_add_owner_inserts_session_operator_and_emits_audit(
    db: Session,
    client: TestClient,
    bob,
) -> None:
    """Bob is on the workspace operator allowlist (per the
    integration-test conftest autouse). Alice (creator + sole
    owner) adds Bob as a co-owner."""
    review_session = _make_session(client, db, code="own-add")
    # Bootstrap Bob's user row so he exists as a workspace operator.
    _seed_user(db, email="bob@example.edu")

    response = client.post(
        f"/operator/sessions/{review_session.id}/owners/add",
        data={"target_email": "bob@example.edu"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}/edit#owners"
    )

    bob_row = db.execute(
        select(User).where(User.email == "bob@example.edu")
    ).scalar_one()
    session_op = db.execute(
        select(SessionOperator).where(
            SessionOperator.session_id == review_session.id,
            SessionOperator.user_id == bob_row.id,
        )
    ).scalar_one()
    assert session_op.role == "owner"

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.owner_added"
        )
    ).scalar_one()
    assert event.detail["refs"]["target_user_id"] == bob_row.id
    assert event.detail["snapshot"]["email"] == "bob@example.edu"
    assert event.detail["session_id"] == review_session.id


def test_add_owner_target_not_in_workspace_303s_with_error(
    db: Session,
    client: TestClient,
) -> None:
    review_session = _make_session(client, db, code="own-non-ws")
    # Seed a user who is NOT a workspace operator.
    _seed_user(db, email="outsider@example.edu", is_operator=False)

    response = client.post(
        f"/operator/sessions/{review_session.id}/owners/add",
        data={"target_email": "outsider@example.edu"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "owners_error=not_in_workspace" in response.headers["location"]


def test_add_owner_target_already_owner_303s_with_error(
    db: Session,
    client: TestClient,
) -> None:
    review_session = _make_session(client, db, code="own-dup")
    # Alice (creator) is already the owner; try to add her again.
    response = client.post(
        f"/operator/sessions/{review_session.id}/owners/add",
        data={"target_email": "alice@example.edu"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "owners_error=already_owner" in response.headers["location"]


def test_add_owner_unknown_email_303s_with_error(
    db: Session,
    client: TestClient,
) -> None:
    review_session = _make_session(client, db, code="own-unknown")
    response = client.post(
        f"/operator/sessions/{review_session.id}/owners/add",
        data={"target_email": "ghost@example.edu"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "owners_error=not_in_workspace" in response.headers["location"]


# --- Remove owner -----------------------------------------------------------


def test_remove_owner_deletes_session_operator_and_emits_audit(
    db: Session,
    client: TestClient,
) -> None:
    review_session = _make_session(client, db, code="own-rm")
    bob_row = _seed_user(db, email="bob@example.edu")
    # Add Bob first.
    client.post(
        f"/operator/sessions/{review_session.id}/owners/add",
        data={"target_email": "bob@example.edu"},
        follow_redirects=False,
    )

    response = client.post(
        f"/operator/sessions/{review_session.id}/owners/{bob_row.id}/remove",
        follow_redirects=False,
    )
    assert response.status_code == 303

    remaining = db.execute(
        select(SessionOperator).where(
            SessionOperator.session_id == review_session.id,
            SessionOperator.user_id == bob_row.id,
        )
    ).scalar_one_or_none()
    assert remaining is None

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "session.owner_removed"
        )
    ).scalar_one()
    assert event.detail["refs"]["target_user_id"] == bob_row.id


def test_remove_last_owner_409s(
    db: Session,
    client: TestClient,
) -> None:
    """Alice is the sole owner of her session. Trying to remove her
    must 409."""
    review_session = _make_session(client, db, code="own-last")
    alice_row = db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()

    response = client.post(
        f"/operator/sessions/{review_session.id}/owners/{alice_row.id}/remove",
        follow_redirects=False,
    )
    assert response.status_code == 409


def test_self_remove_allowed_when_not_last_owner(
    db: Session,
    client: TestClient,
) -> None:
    """Alice can remove herself if Bob is also an owner."""
    review_session = _make_session(client, db, code="own-self-rm")
    _seed_user(db, email="bob@example.edu")
    client.post(
        f"/operator/sessions/{review_session.id}/owners/add",
        data={"target_email": "bob@example.edu"},
        follow_redirects=False,
    )

    alice_row = db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()
    response = client.post(
        f"/operator/sessions/{review_session.id}/owners/{alice_row.id}/remove",
        follow_redirects=False,
    )
    assert response.status_code == 303

    bob_row = db.execute(
        select(User).where(User.email == "bob@example.edu")
    ).scalar_one()
    remaining = db.execute(
        select(SessionOperator).where(
            SessionOperator.session_id == review_session.id
        )
    ).scalars().all()
    assert {r.user_id for r in remaining} == {bob_row.id}


# --- Sys-admin self-add via the relaxed gate -------------------------------


def test_sys_admin_can_self_add_to_session_via_relaxed_gate(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bob is a sys-admin (env-var bootstrap) but isn't a
    session_operator on alice's session. He reaches /edit, then
    submits the Add-owner form pointing at himself. After: he's a
    session_operator and can access the rest of the session
    routes normally."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="own-sa-self")
    # Bob hits /edit first to land his user row via the bootstrap.
    bob_client = make_client(bob)
    bob_client.get(f"/operator/sessions/{review_session.id}/edit")

    response = bob_client.post(
        f"/operator/sessions/{review_session.id}/owners/add",
        data={"target_email": "bob@example.edu"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    bob_row = db.execute(
        select(User).where(User.email == "bob@example.edu")
    ).scalar_one()
    session_op = db.execute(
        select(SessionOperator).where(
            SessionOperator.session_id == review_session.id,
            SessionOperator.user_id == bob_row.id,
        )
    ).scalar_one()
    assert session_op.role == "owner"


# --- Diagnostics: Details link replaces Operators placeholder --------------


def test_diagnostics_row_renders_details_link(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="diag-details")

    response = client.get("/operator/sys-admin/sessions")
    assert response.status_code == 200
    assert (
        f'href="/operator/sessions/{review_session.id}/edit">Details</a>'
        in response.text
    )
    # The old placeholder copy is gone.
    assert "Coming in 16B" not in response.text
