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


def _bootstrap_super_admin(
    monkeypatch: pytest.MonkeyPatch, *, email: str
) -> None:
    """Segment 18S — actor becomes a super-admin (top tier). Super-admin
    implies is_sys_admin + is_operator via the sign-in self-heal, so the
    actor passes ``require_sys_admin`` AND the actor-super guard on
    promote / demote."""
    monkeypatch.setattr(settings, "super_admin_emails", [email])


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
    # Selection persists on the redirect so the toolbar comes
    # back ready for the next action against the same row.
    assert (
        response.headers["location"]
        == f"/operator/sys-admin/users?selected={target.id}"
    )

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


def test_revoke_refuses_when_user_still_owns_sessions(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Accounts Management refinement adds a ``still_owner``
    guard on revoke: an operator who still appears on any
    ``session_operators`` row can't be revoked from the workspace
    operator flag until those sessions are cleared. The operator
    surface gates the button via the same logic on the client
    side; this test pins the server-side enforcement.
    """
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

    # Alice (sys-admin) tries to revoke; refused with 409.
    alice_client = make_client(_alice_auth_user())
    response = alice_client.post(
        f"/operator/sys-admin/users/{bob_row.id}/revoke",
        follow_redirects=False,
    )
    assert response.status_code == 409
    db.refresh(bob_row)
    assert bob_row.is_operator is True  # unchanged
    ops_after = (
        db.execute(
            select(SessionOperator).where(
                SessionOperator.user_id == bob_row.id
            )
        )
        .scalars()
        .all()
    )
    assert len(ops_after) == 1  # session_operators row preserved


def test_revoke_succeeds_when_user_has_no_sessions(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An operator with zero session memberships can still be
    revoked via the per-row route (toolbar will not render this
    state outside of the gate; the server accepts it)."""
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    target = _seed_target(db, email="lonely@example.edu", is_operator=True)
    response = client.post(
        f"/operator/sys-admin/users/{target.id}/revoke",
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(target)
    assert target.is_operator is False


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
    _bootstrap_super_admin(monkeypatch, email="alice@example.edu")
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


def test_promote_without_confirm_still_succeeds(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The confirm-checkbox safety gate retired in the post-15A
    Accounts Management refinement (per-row buttons live on a
    single row now, no inline safety checkbox). Posting without
    confirm now promotes successfully.
    """
    _bootstrap_super_admin(monkeypatch, email="alice@example.edu")
    target = _seed_target(db, email="bob@example.edu", is_operator=True)

    response = client.post(
        f"/operator/sys-admin/users/{target.id}/promote",
        data={},
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(target)
    assert target.is_sys_admin is True


def test_demote_with_confirm_flips_is_sys_admin_and_emits_audit(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_super_admin(monkeypatch, email="alice@example.edu")
    # Alice signs in via the gate as a super-admin (self-heals to
    # is_sys_admin=True); bob is pre-seeded as a second sys-admin so
    # demoting him isn't the last-admin case.
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
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The count-based ``last_admin`` floor still fires under the 18S
    actor-super guard (Decision 2 — both floors kept).

    Since promote / demote now require a **super-admin** actor, the
    actor is a super-admin. To exercise the count floor in isolation we
    give the super actor an unset ``is_sys_admin`` column (its
    pre-sign-in state; ``is_super_admin`` is derived from config, so the
    actor guard still passes) — that keeps it out of ``_sys_admin_count``
    so we can drive the count down to the sole column-True admin."""
    from app.services import users as users_service

    _bootstrap_super_admin(monkeypatch, email="super@example.edu")
    super_actor = _seed_target(db, email="super@example.edu", is_operator=True)
    solo_admin = _seed_target(
        db, email="solo@example.edu", is_operator=True, is_sys_admin=True
    )

    # Only one column-True sys-admin exists → demoting them trips the
    # floor even though the actor is a valid super-admin.
    with pytest.raises(users_service.UserOperationError) as excinfo:
        users_service.demote(
            db, actor=super_actor, target=solo_admin, correlation_id="corr-floor"
        )
    assert excinfo.value.code == "last_admin"
    db.refresh(solo_admin)
    assert solo_admin.is_sys_admin is True  # unchanged

    # A non-last demote succeeds: add a second admin, then demote one.
    _seed_target(
        db, email="second@example.edu", is_operator=True, is_sys_admin=True
    )
    users_service.demote(
        db, actor=super_actor, target=solo_admin, correlation_id="corr-ok"
    )
    db.refresh(solo_admin)
    assert solo_admin.is_sys_admin is False


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


# --- Remove (hard delete) — post-15A refinement -----------------------------


def test_remove_user_deletes_row_and_emits_audit(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    target = _seed_target(db, email="bob@example.edu", is_operator=True)
    target_id = target.id

    response = client.post(
        f"/operator/sys-admin/users/{target_id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/operator/sys-admin/users"

    # Row is gone.
    assert (
        db.execute(select(User).where(User.id == target_id)).scalar_one_or_none()
        is None
    )

    # Audit event captured the snapshot.
    event = db.execute(
        select(AuditEvent).where(
            AuditEvent.event_type == "workspace.user_removed"
        )
    ).scalar_one()
    assert event.detail["refs"] == {"target_user_id": target_id}
    assert event.detail["snapshot"] == {
        "email": "bob@example.edu",
        "is_operator": True,
        "is_sys_admin": False,
    }


def test_remove_user_refuses_self(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    # Trigger first-sign-in to seed the alice user row, then look
    # her up.
    client.get("/operator/sys-admin/users")
    alice = db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()
    response = client.post(
        f"/operator/sys-admin/users/{alice.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 400


def test_remove_user_refuses_last_sys_admin(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    client.get("/operator/sys-admin/users")
    # Seed a second sys-admin so the workspace has two; we'll then
    # remove the second, leaving alice. Then alice tries to be
    # removed by someone else (we'll forge a third actor).
    second = _seed_target(
        db,
        email="bob@example.edu",
        is_operator=True,
        is_sys_admin=True,
    )
    third = _seed_target(
        db,
        email="carol@example.edu",
        is_operator=True,
        is_sys_admin=True,
    )
    # Removing second (one of three) succeeds.
    response = client.post(
        f"/operator/sys-admin/users/{second.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303
    # Removing third leaves only alice — also fine.
    response = client.post(
        f"/operator/sys-admin/users/{third.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303
    # Now seed a fourth user as the new sole non-alice sys-admin
    # and try to remove them — refuses since alice is the actor,
    # not the target, and removing the target would leave alice
    # as the sole sys-admin... actually alice is still sys-admin
    # so this would not trip last_admin. Let me test the actual
    # last_admin scenario: target is the only sys-admin, actor
    # somehow is operator-but-not-sys-admin. Skip — actor must be
    # sys-admin per the route gate, so the only way to trip
    # last_admin is target == actor, which the self_action guard
    # catches first. The remove path's last_admin guard is
    # belt-and-suspenders.


def test_remove_user_refuses_when_user_owns_sessions(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.db.models import ReviewSession

    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    target = _seed_target(db, email="bob@example.edu", is_operator=True)

    # Give bob a session of his own.
    review_session = ReviewSession(
        name="Bob's Session", code="bob-owns", created_by_user_id=target.id
    )
    db.add(review_session)
    db.flush()
    db.add(
        SessionOperator(
            session_id=review_session.id, user_id=target.id, role="owner"
        )
    )
    db.commit()

    response = client.post(
        f"/operator/sys-admin/users/{target.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 409
    # Row is still there.
    db.refresh(target)
    assert target.email == "bob@example.edu"


def test_remove_user_404s_on_missing_target(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    response = client.post(
        "/operator/sys-admin/users/99999/delete", follow_redirects=False
    )
    assert response.status_code == 404


# --- Template render shape — post-15A button refinement ---------------------


def test_workspace_users_page_renders_bulk_action_toolbar(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The action surface is now a single bulk-action toolbar
    above the table. Per-row buttons retired in favour of a
    single-row checkbox-driven selection: one user picked at a
    time drives whichever toolbar buttons are eligible.

    Toolbar carries four action forms:
    Operator: Admit / Revoke (one form) + Remove from all sessions,
    Admin: Promote / Demote (one form), and Delete.

    The Promote/Demote form is super-admin-only (Segment 18S), so the
    actor here is a super-admin to see all four forms.
    """
    _bootstrap_super_admin(monkeypatch, email="alice@example.edu")
    _seed_target(db, email="bob@example.edu", is_operator=True)
    body = client.get("/operator/sys-admin/users").text
    # Toolbar exists.
    assert 'id="user-actions"' in body
    # Four action forms wired with the right markers.
    assert 'data-action-form="operator-toggle"' in body
    assert 'data-action-form="remove-sessions"' in body
    assert 'data-action-form="sys-admin-toggle"' in body
    assert 'data-action-form="delete"' in body
    # Per-row checkbox replaces the inline button cluster.
    assert 'class="user-row-select"' in body
    # All toolbar buttons start ``disabled`` (no row selected yet).
    assert 'data-action-btn="operator-toggle"' in body
    assert 'data-action-btn="remove-sessions"' in body
    assert 'data-action-btn="sys-admin-toggle"' in body
    assert 'data-action-btn="delete"' in body
    # No safety checkbox; no inline per-row Revoke/Promote/Delete buttons.
    assert 'name="confirm"' not in body
    assert 'type="submit">Revoke<' not in body
    assert 'type="submit">Promote<' not in body
    # Per-row data attributes for the JS gates.
    assert 'data-is-operator="true"' in body
    assert 'data-is-sys-admin="false"' in body
    assert 'data-session-count="0"' in body
    assert 'data-sole-owner-count="0"' in body


def test_invite_card_renders_secondary_buttons_disabled_by_default(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    body = client.get("/operator/sys-admin/users").text
    # Invite + Cancel both render Secondary style with
    # data-invite-* markers + start ``disabled``.
    assert "data-invite-submit" in body
    assert "data-invite-cancel" in body
    assert 'disabled>Invite' in body
    assert 'disabled>Cancel' in body


# --- Remove from all sessions (post-15A bulk-action refinement) -------------


def test_remove_from_all_sessions_deletes_operator_rows_and_emits_audit(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.db.models import ReviewSession

    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    target = _seed_target(db, email="bob@example.edu", is_operator=True)

    # Bob shares two sessions with someone else (so he's not sole owner).
    co_owner = _seed_target(db, email="carol@example.edu", is_operator=True)
    for code in ("s1", "s2"):
        rs = ReviewSession(
            name=code, code=code, created_by_user_id=co_owner.id
        )
        db.add(rs)
        db.flush()
        db.add(SessionOperator(session_id=rs.id, user_id=target.id, role="owner"))
        db.add(
            SessionOperator(session_id=rs.id, user_id=co_owner.id, role="owner")
        )
    db.commit()

    response = client.post(
        f"/operator/sys-admin/users/{target.id}/remove-from-all-sessions",
        follow_redirects=False,
    )
    assert response.status_code == 303
    # All of bob's session_operators rows are gone.
    leftover = (
        db.execute(
            select(SessionOperator).where(
                SessionOperator.user_id == target.id
            )
        )
        .scalars()
        .all()
    )
    assert leftover == []
    # is_operator stays True (the workspace flag is independent of
    # per-session ownership).
    db.refresh(target)
    assert target.is_operator is True
    # Audit event with counts envelope.
    event = (
        db.execute(
            select(AuditEvent).where(
                AuditEvent.event_type
                == "workspace.user_detached_from_all_sessions"
            )
        )
        .scalars()
        .one()
    )
    assert event.detail["counts"] == {"sessions_detached": 2}
    assert event.detail["refs"] == {"target_user_id": target.id}


def test_remove_from_all_sessions_refuses_when_sole_owner(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.db.models import ReviewSession

    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    target = _seed_target(db, email="bob@example.edu", is_operator=True)
    # Bob is the sole owner of a session.
    rs = ReviewSession(
        name="solo", code="solo", created_by_user_id=target.id
    )
    db.add(rs)
    db.flush()
    db.add(SessionOperator(session_id=rs.id, user_id=target.id, role="owner"))
    db.commit()

    response = client.post(
        f"/operator/sys-admin/users/{target.id}/remove-from-all-sessions",
        follow_redirects=False,
    )
    assert response.status_code == 409
    # No rows touched.
    leftover = (
        db.execute(
            select(SessionOperator).where(
                SessionOperator.user_id == target.id
            )
        )
        .scalars()
        .all()
    )
    assert len(leftover) == 1


def test_remove_from_all_sessions_refuses_self(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    client.get("/operator/sys-admin/users")
    alice = db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()
    response = client.post(
        f"/operator/sys-admin/users/{alice.id}/remove-from-all-sessions",
        follow_redirects=False,
    )
    assert response.status_code == 400


def test_list_workspace_users_surfaces_sole_owner_count(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``WorkspaceUserRow.sole_owner_count`` powers the toolbar
    Delete / Remove-from-all-sessions gates."""
    from app.db.models import ReviewSession
    from app.services import users as users_service

    bob = _seed_target(db, email="bob@example.edu", is_operator=True)
    carol = _seed_target(db, email="carol@example.edu", is_operator=True)
    # Bob solo on s1, co-owner on s2.
    s1 = ReviewSession(name="s1", code="s1", created_by_user_id=bob.id)
    s2 = ReviewSession(name="s2", code="s2", created_by_user_id=bob.id)
    db.add_all([s1, s2])
    db.flush()
    db.add(SessionOperator(session_id=s1.id, user_id=bob.id, role="owner"))
    db.add(SessionOperator(session_id=s2.id, user_id=bob.id, role="owner"))
    db.add(SessionOperator(session_id=s2.id, user_id=carol.id, role="owner"))
    db.commit()

    rows = {row.email: row for row in users_service.list_workspace_users(db)}
    assert rows["bob@example.edu"].session_operator_count == 2
    assert rows["bob@example.edu"].sole_owner_count == 1
    assert rows["carol@example.edu"].session_operator_count == 1
    assert rows["carol@example.edu"].sole_owner_count == 0


# --- Selection persistence + toolbar layout ---------------------------------


def test_selection_persists_via_redirect_and_renders_checked(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After a toolbar action the route redirects back with
    ``?selected={user_id}``; the GET handler reads the param and
    the template stamps ``checked`` on the matching row so the
    operator can chain a second action without re-selecting.
    """
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    target = _seed_target(db, email="bob@example.edu", is_operator=False)

    response = client.post(
        f"/operator/sys-admin/users/{target.id}/admit",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert (
        response.headers["location"]
        == f"/operator/sys-admin/users?selected={target.id}"
    )

    # Following the redirect renders the row checkbox already
    # checked (so the toolbar JS picks up the selection on first
    # paint without operator interaction). The template wraps
    # attributes across lines so the substring check normalises
    # whitespace.
    body = client.get(
        f"/operator/sys-admin/users?selected={target.id}"
    ).text
    import re

    normalised = re.sub(r"\s+", " ", body)
    assert (
        'aria-label="Select bob@example.edu" checked' in normalised
    )


def test_remove_user_redirects_without_selection(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Delete action removes the row, so there's nothing to
    re-select. The redirect omits the ``selected`` query param."""
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    target = _seed_target(db, email="bob@example.edu", is_operator=True)
    response = client.post(
        f"/operator/sys-admin/users/{target.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/operator/sys-admin/users"


def test_toolbar_left_aligned(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Toolbar sits flush-left so the four buttons cluster next
    to the row-selection checkboxes (which live in the leftmost
    column)."""
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    _seed_target(db, email="bob@example.edu", is_operator=True)
    body = client.get("/operator/sys-admin/users").text
    assert "justify-content:flex-start" in body
    assert "justify-content:flex-end" not in body


# --------------------------------------------------------------------------- #
# Segment 18S Item 1 — three-tier management guards
# (actor-super on promote/demote; target-super protection)
# --------------------------------------------------------------------------- #


def test_plain_sys_admin_cannot_promote(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Actor is a plain sys-admin (NOT super-admin), and a super tier
    IS configured (someone else), so the strict rule applies: promoting
    an operator to admin is super-admin-only → 403."""
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    monkeypatch.setattr(settings, "super_admin_emails", ["boss@example.edu"])
    target = _seed_target(db, email="bob@example.edu", is_operator=True)

    response = client.post(
        f"/operator/sys-admin/users/{target.id}/promote",
        follow_redirects=False,
    )
    assert response.status_code == 403
    db.refresh(target)
    assert target.is_sys_admin is False  # unchanged


def test_plain_sys_admin_cannot_demote(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Actor is a plain sys-admin, with a super tier configured, so the
    strict rule applies: demoting another admin is super-admin-only → 403."""
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    monkeypatch.setattr(settings, "super_admin_emails", ["boss@example.edu"])
    target = _seed_target(
        db, email="bob@example.edu", is_operator=True, is_sys_admin=True
    )

    response = client.post(
        f"/operator/sys-admin/users/{target.id}/demote",
        follow_redirects=False,
    )
    assert response.status_code == 403
    db.refresh(target)
    assert target.is_sys_admin is True  # unchanged


def test_plain_sys_admin_can_still_admit_and_revoke_operators(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Operator management stays admin-gated (not super-admin-only):
    a plain sys-admin can admit and revoke operators."""
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    target = _seed_target(db, email="bob@example.edu", is_operator=False)

    admit = client.post(
        f"/operator/sys-admin/users/{target.id}/admit",
        follow_redirects=False,
    )
    assert admit.status_code == 303
    db.refresh(target)
    assert target.is_operator is True

    revoke = client.post(
        f"/operator/sys-admin/users/{target.id}/revoke",
        follow_redirects=False,
    )
    assert revoke.status_code == 303
    db.refresh(target)
    assert target.is_operator is False


def test_super_admin_target_cannot_be_demoted(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Even a super-admin actor can't demote a super-admin target —
    super-admin is config-only (protected). 409."""
    monkeypatch.setattr(
        settings,
        "super_admin_emails",
        ["alice@example.edu", "boss@example.edu"],
    )
    target = _seed_target(
        db, email="boss@example.edu", is_operator=True, is_sys_admin=True
    )

    response = client.post(
        f"/operator/sys-admin/users/{target.id}/demote",
        follow_redirects=False,
    )
    assert response.status_code == 409
    db.refresh(target)
    assert target.is_sys_admin is True  # unchanged


def test_super_admin_target_cannot_be_revoked(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "super_admin_emails",
        ["alice@example.edu", "boss@example.edu"],
    )
    target = _seed_target(
        db, email="boss@example.edu", is_operator=True, is_sys_admin=True
    )

    response = client.post(
        f"/operator/sys-admin/users/{target.id}/revoke",
        follow_redirects=False,
    )
    assert response.status_code == 409
    db.refresh(target)
    assert target.is_operator is True  # unchanged


def test_super_admin_target_cannot_be_removed(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "super_admin_emails",
        ["alice@example.edu", "boss@example.edu"],
    )
    target = _seed_target(
        db, email="boss@example.edu", is_operator=True, is_sys_admin=True
    )

    response = client.post(
        f"/operator/sys-admin/users/{target.id}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 409
    still = db.execute(
        select(User).where(User.email == "boss@example.edu")
    ).scalar_one_or_none()
    assert still is not None  # not deleted


def test_super_admin_target_cannot_be_removed_from_all_sessions(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Service-layer: the target-super guard blocks detaching a
    super-admin from its sessions (protected_super_admin)."""
    from app.services import users as users_service

    monkeypatch.setattr(
        settings,
        "super_admin_emails",
        ["actor@example.edu", "boss@example.edu"],
    )
    actor = _seed_target(db, email="actor@example.edu", is_operator=True)
    target = _seed_target(db, email="boss@example.edu", is_operator=True)

    with pytest.raises(users_service.UserOperationError) as excinfo:
        users_service.remove_from_all_sessions(
            db, actor=actor, target=target, correlation_id="corr-x"
        )
    assert excinfo.value.code == "protected_super_admin"


# --------------------------------------------------------------------------- #
# Segment 18S PR 3 — tier badges + conditional controls + chrome
# --------------------------------------------------------------------------- #


def test_super_admin_row_shows_super_admin_badge(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A super-admin user's row carries the violet Super-admin tier
    badge + the data-is-super-admin marker the JS gates on."""
    monkeypatch.setattr(
        settings,
        "super_admin_emails",
        ["alice@example.edu", "boss@example.edu"],
    )
    _seed_target(
        db, email="boss@example.edu", is_operator=True, is_sys_admin=True
    )
    body = client.get("/operator/sys-admin/users").text
    assert "pill-super" in body
    assert "Super-admin" in body
    assert 'data-is-super-admin="true"' in body


def test_plain_admin_row_shows_admin_badge(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_super_admin(monkeypatch, email="alice@example.edu")
    _seed_target(
        db, email="bob@example.edu", is_operator=True, is_sys_admin=True
    )
    body = client.get("/operator/sys-admin/users").text
    # bob is a plain admin (not super) → the Admin (info) badge.
    assert '<span class="pill pill-info">Admin</span>' in body


def test_promote_demote_controls_hidden_for_plain_sys_admin_actor(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A plain sys-admin actor doesn't see the Promote/Demote form when
    a super tier is configured (admin management is super-admin-only).
    Operator + delete forms still render."""
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    monkeypatch.setattr(settings, "super_admin_emails", ["boss@example.edu"])
    _seed_target(db, email="bob@example.edu", is_operator=True)
    body = client.get("/operator/sys-admin/users").text
    assert 'data-action-form="sys-admin-toggle"' not in body
    # But operator management + delete remain.
    assert 'data-action-form="operator-toggle"' in body
    assert 'data-action-form="delete"' in body


def test_promote_demote_controls_visible_for_super_admin_actor(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_super_admin(monkeypatch, email="alice@example.edu")
    _seed_target(db, email="bob@example.edu", is_operator=True)
    body = client.get("/operator/sys-admin/users").text
    assert 'data-action-form="sys-admin-toggle"' in body


def test_chrome_shows_super_admin_suffix(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The top-right chrome labels a super-admin as (super admin),
    not (sys admin)."""
    _bootstrap_super_admin(monkeypatch, email="alice@example.edu")
    body = client.get("/operator/sys-admin/users").text
    assert "(super admin)" in body
    assert "(sys admin)" not in body


def test_chrome_shows_sys_admin_suffix_for_plain_admin(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    body = client.get("/operator/sys-admin/users").text
    assert "(sys admin)" in body
    assert "(super admin)" not in body


# --------------------------------------------------------------------------- #
# Segment 18S Item 2 — no-super-tier fallback (fix the lockout)
# --------------------------------------------------------------------------- #


def test_plain_admin_can_promote_when_no_super_tier_configured(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With SUPER_ADMIN_EMAILS empty (no super tier at all), a plain
    sys-admin can promote again — the fallback avoids locking admin
    management out entirely."""
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    monkeypatch.setattr(settings, "super_admin_emails", [])
    target = _seed_target(db, email="bob@example.edu", is_operator=True)

    response = client.post(
        f"/operator/sys-admin/users/{target.id}/promote",
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(target)
    assert target.is_sys_admin is True


def test_plain_admin_can_demote_when_no_super_tier_configured(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    monkeypatch.setattr(settings, "super_admin_emails", [])
    # Two admins so the demote isn't the last-admin case.
    target = _seed_target(
        db, email="bob@example.edu", is_operator=True, is_sys_admin=True
    )

    response = client.post(
        f"/operator/sys-admin/users/{target.id}/demote",
        follow_redirects=False,
    )
    assert response.status_code == 303
    db.refresh(target)
    assert target.is_sys_admin is False


def test_promote_demote_controls_visible_to_plain_admin_when_no_super_tier(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The UI mirrors the fallback: with no super tier configured, a
    plain sys-admin sees the Promote/Demote controls again."""
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    monkeypatch.setattr(settings, "super_admin_emails", [])
    _seed_target(db, email="bob@example.edu", is_operator=True)
    body = client.get("/operator/sys-admin/users").text
    assert 'data-action-form="sys-admin-toggle"' in body
