"""Coverage for Segment 16B PR 2 — per-session owner management.

Exercises the Owners section, which lives on Session Home's config card
(``#config-owners-card``) since 18R Item 4 retired the Edit page:

- Owner can add another workspace operator as a co-owner.
- Owner can remove a non-self owner.
- Owner can self-remove when another owner exists.
- Last-owner remove → 409.
- Add target not on the workspace allowlist → 303 with
  ``owners_error=not_in_workspace``.
- Add target already an owner → 303 with
  ``owners_error=already_owner``.
- Segment 18S Item 3: a sys-admin who isn't a session_operator is
  DENIED the session config surface (and lobby-edit / owners-remove);
  they self-add as owner via the Diagnostics "Manage"/adopt action, then
  have full operator access via the normal session-operator path.
  owners/add is self-only for a non-owner sys-admin; clone stays allowed.
- Audit events emitted with correct envelope.
- Plain non-owner operator still 403s on the session config surface.
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
    # 18R Item 4 — owners live on Session Home's config Owners sub-card.
    response = client.get(f"/operator/sessions/{review_session.id}?editing=1")
    assert response.status_code == 200
    # Owners sub-card present; creator (alice) is the single owner.
    assert 'id="config-owners-card"' in response.text
    assert "alice@example.edu" in response.text


def test_edit_page_403s_for_plain_non_member_operator(
    db: Session,
    client: TestClient,
    make_client,
    bob,
) -> None:
    review_session = _make_session(client, db, code="own-403")
    bob_client = make_client(bob)
    # 18R Item 4 — Session Home is the config surface; a non-owner 403s.
    response = bob_client.get(
        f"/operator/sessions/{review_session.id}",
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_sys_admin_non_member_denied_edit_until_adopt(
    db: Session,
    client: TestClient,
    make_client,
    bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Segment 18S Item 3 — editing a non-owned session requires ownership.
    Sys-admin Bob (not a session_operator on alice's session) is **denied**
    Session Home until he self-adds as owner via the Diagnostics adopt
    action, after which Home renders (18R Item 4 retired the Edit page)."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="own-sa")

    bob_client = make_client(bob)
    # Denied before adopting.
    denied = bob_client.get(f"/operator/sessions/{review_session.id}")
    assert denied.status_code == 403

    # The audited elevation door: self-add as owner, land on Home.
    adopt = bob_client.post(
        f"/operator/sys-admin/sessions/{review_session.id}/adopt",
        follow_redirects=False,
    )
    assert adopt.status_code == 303
    assert adopt.headers["location"] == f"/operator/sessions/{review_session.id}"

    # Now an owner → Home renders with the Owners sub-card.
    response = bob_client.get(f"/operator/sessions/{review_session.id}?editing=1")
    assert response.status_code == 200
    assert 'id="config-owners-card"' in response.text


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
    # 18R Item 4 Slice 4 — owner add/remove now land on Session Home's config
    # card in edit mode (was the Edit page's #owners anchor).
    assert response.headers["location"] == (
        f"/operator/sessions/{review_session.id}?editing=1#config-owners-card"
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


def test_config_owners_card_renders_add_form_when_candidates_exist(
    db: Session,
    client: TestClient,
    bob,
) -> None:
    """18R Item 4 Slice 4 — with a second workspace operator available, the
    Session Home config Owners sub-card renders the wired Add-owner form."""
    review_session = _make_session(client, db, code="own-addform")
    _seed_user(db, email="bob@example.edu")

    body = client.get(
        f"/operator/sessions/{review_session.id}?editing=1"
    ).text
    config_pos = body.find('id="session-config"')
    card = body[config_pos:body.find("window.sessionConfig", config_pos)]

    assert 'id="config-add-owner-email"' in card
    assert 'name="target_email"' in card
    assert (
        f'action="/operator/sessions/{review_session.id}/owners/add"' in card
    )
    # Bob is offered as a candidate in the datalist.
    assert "bob@example.edu" in card


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
    session_operator on alice's session. He submits the Add-owner form
    pointing at himself. After: he's a session_operator and can access
    the rest of the session routes normally."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="own-sa-self")
    # Bob hits a session route first to land his user row via the bootstrap
    # (get_or_create_user runs even though the operator gate 403s him).
    bob_client = make_client(bob)
    bob_client.get(f"/operator/sessions/{review_session.id}")

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


def test_diagnostics_row_renders_manage_adopt_action(
    db: Session,
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Segment 18S Item 3 — the Diagnostics row's edit entry is a
    "Manage" POST to the adopt route (self-add as owner → open), not a
    back-door GET link to /edit."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="diag-details")

    response = client.get("/operator/sys-admin/sessions")
    assert response.status_code == 200
    assert (
        f'action="/operator/sys-admin/sessions/{review_session.id}/adopt"'
        in response.text
    )
    assert ">Manage</button>" in response.text
    # The old back-door edit link is gone.
    assert f'/operator/sessions/{review_session.id}/edit">Details' not in response.text


# --------------------------------------------------------------------------- #
# Segment 18S Item 3 — sys-admin cross-session writes require ownership
# --------------------------------------------------------------------------- #


def test_non_owner_sys_admin_denied_edit_submit(
    db: Session, client: TestClient, make_client, bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="deny-edit")
    # 18R Item 4 — config edits go through /config (require_session_operator).
    resp = make_client(bob).post(
        f"/operator/sessions/{review_session.id}/config",
        data={"name": "x", "code": "deny-edit", "description": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 403


def test_non_owner_sys_admin_denied_lobby_edit(
    db: Session, client: TestClient, make_client, bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="deny-lobby")
    resp = make_client(bob).post(
        f"/operator/sessions/{review_session.id}/lobby-edit",
        data={"name": "x", "code": "deny-lobby", "tags": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 403


def test_non_owner_sys_admin_denied_owners_remove(
    db: Session, client: TestClient, make_client, bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="deny-remove")
    # The per-session gate denies before the target user_id matters.
    resp = make_client(bob).post(
        f"/operator/sessions/{review_session.id}/owners/1/remove",
        follow_redirects=False,
    )
    assert resp.status_code == 403


def test_owners_add_self_only_blocks_adding_other(
    db: Session, client: TestClient, make_client, bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-owner sys-admin may add only themselves; adding someone
    else is refused with the self_only owners-error."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="self-only")
    carol = _seed_user(db, email="carol@example.edu")

    resp = make_client(bob).post(
        f"/operator/sessions/{review_session.id}/owners/add",
        data={"target_email": "carol@example.edu"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert "owners_error=self_only" in resp.headers["location"]
    # Carol was not added.
    added = db.execute(
        select(SessionOperator).where(
            SessionOperator.session_id == review_session.id,
            SessionOperator.user_id == carol.id,
        )
    ).scalar_one_or_none()
    assert added is None


def test_non_owner_sys_admin_can_still_clone(
    db: Session, client: TestClient, make_client, bob,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["bob@example.edu"])
    review_session = _make_session(client, db, code="clone-ok")
    before = db.execute(select(SessionOperator.id)).all()
    resp = make_client(bob).post(
        f"/operator/sessions/{review_session.id}/clone",
        data={"mode": "config"},
        follow_redirects=False,
    )
    assert resp.status_code == 303
    after = db.execute(select(SessionOperator.id)).all()
    assert len(after) > len(before)  # a new owned clone was created


def test_adopt_idempotent_when_already_owner(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Adopting a session you already own is a no-op 303 (no duplicate
    owner, no error)."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _make_session(client, db, code="adopt-idem")
    resp = client.post(
        f"/operator/sys-admin/sessions/{review_session.id}/adopt",
        follow_redirects=False,
    )
    assert resp.status_code == 303
    owners = db.execute(
        select(SessionOperator).where(
            SessionOperator.session_id == review_session.id
        )
    ).scalars().all()
    assert len(owners) == 1  # still just alice
