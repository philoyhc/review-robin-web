"""Coverage for the Segment 16A PR 6 Accounts Management tab.

Exercises F6-F9:
- Admit / Revoke (is_operator toggle, one-click) + audit event.
- Promote / Demote (is_sys_admin toggle, requires confirm) + audit
  event. Missing confirm → 400.
- Last-admin-demote guard refuses to leave the workspace without a
  sys-admin (409).
- Self-actions are blocked outright (400).
- Revoking an operator who's on N sessions preserves their
  ``session_operators`` rows.
- Invite by email pre-seeds a users row + emits the
  ``workspace.user_invited`` audit event. Duplicates 303 with an
  invite_error query param.
- Non-sys-admin GET /operator/sys-admin/users → 403.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditEvent, SessionOperator, User


def _bootstrap_sys_admin(
    monkeypatch: pytest.MonkeyPatch, *, email: str
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", [email])


def _seed_target(
    db: Session,
    *,
    email: str,
    is_operator: bool = False,
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


def test_users_page_renders_for_sys_admin(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    _seed_target(db, email="bob@example.edu", is_operator=True)
    response = client.get("/operator/sys-admin/users")
    assert response.status_code == 200
    assert "<h1>Admin</h1>" in response.text
    assert "Accounts Management" in response.text
    assert "bob@example.edu" in response.text


def test_users_page_403s_for_plain_operator(
    db: Session,
    client: TestClient,
) -> None:
    response = client.get("/operator/sys-admin/users", follow_redirects=False)
    assert response.status_code == 403


# --- Admit / Revoke (F6) ---------------------------------------------------


def test_admit_flips_is_operator_and_emits_audit(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    target = _seed_target(db, email="bob@example.edu", is_operator=False)

    response = client.post(
        f"/operator/sys-admin/users/{target.id}/admit", follow_redirects=False
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/operator/sys-admin/users"

    db.refresh(target)
    assert target.is_operator is True

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "workspace.operator_admitted"
        )
    ).scalar_one()
    assert event.detail["refs"] == {"target_user_id": target.id}
    assert event.detail["changes"] == {"is_operator": [False, True]}


def test_revoke_flips_is_operator_back_and_emits_audit(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    target = _seed_target(db, email="bob@example.edu", is_operator=True)

    response = client.post(
        f"/operator/sys-admin/users/{target.id}/revoke", follow_redirects=False
    )
    assert response.status_code == 303

    db.refresh(target)
    assert target.is_operator is False

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "workspace.operator_revoked"
        )
    ).scalar_one()
    assert event.detail["refs"] == {"target_user_id": target.id}
    assert event.detail["changes"] == {"is_operator": [True, False]}


def test_revoke_preserves_session_operators(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Revoking bob's operator status must NOT cascade-delete his
    session_operators rows — re-admitting later restores access
    without re-adding to sessions."""
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")

    bob_client = make_client(bob)
    bob_client.post(
        "/operator/sessions",
        data={"name": "Bob", "code": "bob-1"},
        follow_redirects=False,
    )
    bob_row = db.execute(
        select(User).where(User.email == "bob@example.edu")
    ).scalar_one()
    before_count = db.execute(
        select(SessionOperator).where(SessionOperator.user_id == bob_row.id)
    ).scalars().all()
    assert len(before_count) == 1

    # Alice (sys-admin) revokes Bob's operator status.
    alice_client = make_client(_alice_auth_user())
    alice_client.post(
        f"/operator/sys-admin/users/{bob_row.id}/revoke",
        follow_redirects=False,
    )
    after_count = db.execute(
        select(SessionOperator).where(SessionOperator.user_id == bob_row.id)
    ).scalars().all()
    assert len(after_count) == 1  # session_operators row preserved


def _alice_auth_user():
    from app.auth.identity import AuthenticatedUser

    return AuthenticatedUser(
        principal_id="alice-oid",
        email="alice@example.edu",
        name="Alice Example",
        provider="aad",
    )


# --- Promote / Demote (F7) -------------------------------------------------


def test_promote_with_confirm_flips_is_sys_admin_and_emits_audit(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    target = _seed_target(db, email="bob@example.edu", is_operator=True)

    response = client.post(
        f"/operator/sys-admin/users/{target.id}/promote",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.refresh(target)
    assert target.is_sys_admin is True

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "sys_admin.role_promoted"
        )
    ).scalar_one()
    assert event.detail["refs"] == {"target_user_id": target.id}
    assert event.detail["changes"] == {"is_sys_admin": [False, True]}


def test_promote_without_confirm_400s(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    target = _seed_target(db, email="bob@example.edu", is_operator=True)

    response = client.post(
        f"/operator/sys-admin/users/{target.id}/promote",
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 400
    db.refresh(target)
    assert target.is_sys_admin is False  # unchanged


def test_demote_with_confirm_flips_is_sys_admin_and_emits_audit(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    # Alice will sign in via the gate; bob is pre-seeded as a
    # second sys-admin so demoting him isn't the last-admin case.
    target = _seed_target(
        db, email="bob@example.edu", is_operator=True, is_sys_admin=True
    )

    response = client.post(
        f"/operator/sys-admin/users/{target.id}/demote",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 303

    db.refresh(target)
    assert target.is_sys_admin is False

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "sys_admin.role_demoted"
        )
    ).scalar_one()
    assert event.detail["refs"] == {"target_user_id": target.id}


# --- Last-admin-demote guard (F7) ------------------------------------------


def test_demote_last_sys_admin_at_service_layer(
    db: Session,
    make_client,
    alice,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct service-call covers the 'sole sys-admin' invariant
    cleanly. Route-level call is awkward to exercise because the
    actor must themselves be sys-admin (so by definition isn't
    the sole admin unless they ARE the target — which the
    self-action guard catches first)."""
    from app.services import users as users_service

    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    alice_client = make_client(alice)
    alice_client.get("/operator/sys-admin/users")  # bootstrap alice

    alice_row = db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()
    second_admin = _seed_target(
        db, email="second@example.edu", is_operator=True, is_sys_admin=True
    )

    # Now demote the second admin via service (actor is alice; not
    # the self-action case). After this, alice is sole admin.
    users_service.demote(
        db,
        actor=alice_row,
        target=second_admin,
        correlation_id="corr-1",
    )

    # Try to demote alice via service with second_admin as actor —
    # but second is no longer admin, so the constraint is "if I
    # demote alice, the count goes to zero". Need a third admin
    # to be actor.
    third_admin = _seed_target(
        db, email="third@example.edu", is_operator=True, is_sys_admin=True
    )
    # Now alice + third are admins. Demote alice (count -> 1).
    users_service.demote(
        db, actor=third_admin, target=alice_row, correlation_id="corr-2"
    )
    db.refresh(third_admin)
    db.refresh(alice_row)
    assert third_admin.is_sys_admin is True
    assert alice_row.is_sys_admin is False

    # Now third is the sole admin. Demoting them must raise.
    # Use a non-admin actor — guard only checks sole-admin
    # state, not whether actor is admin.
    operator_actor = _seed_target(
        db, email="op@example.edu", is_operator=True, is_sys_admin=False
    )
    with pytest.raises(users_service.UserOperationError) as excinfo:
        users_service.demote(
            db, actor=operator_actor, target=third_admin, correlation_id="corr-3"
        )
    assert excinfo.value.code == "last_admin"
    db.refresh(third_admin)
    assert third_admin.is_sys_admin is True  # unchanged


# --- Self-actions blocked (F6/F7) ------------------------------------------


def test_self_admit_blocked(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Alice signs in, gets her users row via the bootstrap. Hitting
    the admit endpoint with her own id returns 400."""
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    client.get("/operator/sys-admin/users")  # bootstrap alice

    alice_row = db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()
    response = client.post(
        f"/operator/sys-admin/users/{alice_row.id}/admit",
        follow_redirects=False,
    )
    assert response.status_code == 400


def test_self_demote_blocked(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    client.get("/operator/sys-admin/users")
    alice_row = db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()
    response = client.post(
        f"/operator/sys-admin/users/{alice_row.id}/demote",
        data={"confirm": "true"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    db.refresh(alice_row)
    assert alice_row.is_sys_admin is True  # unchanged


# --- Invite by email -------------------------------------------------------


def test_invite_creates_user_row_and_emits_audit(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    response = client.post(
        "/operator/sys-admin/users/invite",
        data={"email": "new@example.edu"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/operator/sys-admin/users"

    new_row = db.execute(
        select(User).where(User.email == "new@example.edu")
    ).scalar_one()
    assert new_row.is_operator is True
    assert new_row.is_sys_admin is False

    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "workspace.user_invited"
        )
    ).scalar_one()
    assert event.detail["refs"] == {"target_user_id": new_row.id}
    assert event.detail["snapshot"]["email"] == "new@example.edu"


def test_invite_as_sys_admin_flips_both_flags(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    client.post(
        "/operator/sys-admin/users/invite",
        data={"email": "newadmin@example.edu", "invite_as_sys_admin": "true"},
        follow_redirects=False,
    )
    new_row = db.execute(
        select(User).where(User.email == "newadmin@example.edu")
    ).scalar_one()
    assert new_row.is_operator is True
    assert new_row.is_sys_admin is True


def test_invite_duplicate_email_303s_with_error(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    _seed_target(db, email="existing@example.edu", is_operator=True)
    response = client.post(
        "/operator/sys-admin/users/invite",
        data={"email": "existing@example.edu"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "invite_error=duplicate" in response.headers["location"]


def test_invite_invalid_email_303s_with_error(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    response = client.post(
        "/operator/sys-admin/users/invite",
        data={"email": "not-an-email"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "invite_error=invalid_email" in response.headers["location"]


# --- Bootstrap: pre-seeded row picked up on first sign-in ------------------


def test_pre_seeded_user_signs_in_through_existing_row(
    db: Session,
    make_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pre-seed a users row via the invite path; their first Entra
    sign-in matches by email and grants operator access without
    going through env-var bootstrap."""
    from app.auth.identity import AuthenticatedUser

    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    # Use alice's client to invite a new user.
    invitee_client = make_client(
        AuthenticatedUser(
            principal_id="alice-oid",
            email="alice@example.edu",
            name="Alice",
            provider="aad",
        )
    )
    invitee_client.post(
        "/operator/sys-admin/users/invite",
        data={"email": "invited@example.edu"},
        follow_redirects=False,
    )

    invited_user = AuthenticatedUser(
        principal_id="invited-oid",
        email="invited@example.edu",
        name="Invited",
        provider="aad",
    )
    invited_client = make_client(invited_user)
    # Make sure the invitee can reach an operator route directly —
    # the pre-seeded is_operator=True passes the gate.
    response = invited_client.get("/operator/sessions")
    assert response.status_code == 200


# --- 404 on missing target -------------------------------------------------


def test_admit_404s_on_missing_target(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    response = client.post(
        "/operator/sys-admin/users/99999/admit", follow_redirects=False
    )
    assert response.status_code == 404
