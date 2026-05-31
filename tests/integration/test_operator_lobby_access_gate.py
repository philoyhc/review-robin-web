"""Regression coverage for the operator-lobby access policy.

The contract: only **session owners** (``session_operators``
membership) and **sys-admins** can reach the operator surface.
Being a reviewer, reviewee, or observer on a session does NOT
grant operator-side access; participants belong on ``/me``.

This file pins both layers of the gate against the actual
``/operator/sessions`` URL (not the synthetic ``__test`` route
in ``test_operator_allowlist_gate.py``):

1. Workspace gate (``require_operator``) — a user not on the
   operator / sys-admin allowlist is redirected to
   ``/request-access`` even if they're a participant on
   sessions.
2. Per-session gate (``require_session_operator``) — a
   workspace-allowlisted operator who isn't a SessionOperator
   member of session X is 403'd from
   ``/operator/sessions/{X}/*``; participants alone don't
   confer that membership.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser, get_current_user
from app.config import settings
from app.db.models import (
    Observer,
    Reviewee,
    Reviewer,
    ReviewSession,
)
from app.db.session import get_db
from app.main import app


def _make_client(
    db: Session, user: AuthenticatedUser
) -> TestClient:
    def override_get_db() -> Iterator[Session]:
        yield db

    def override_get_current_user() -> AuthenticatedUser:
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return TestClient(app, follow_redirects=False)


@pytest.fixture(autouse=True)
def _clear_overrides() -> Iterator[None]:
    try:
        yield
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def auth_carol() -> AuthenticatedUser:
    """A user who is NOT on the workspace operator / sys-admin
    allowlist seeded by the integration conftest. Use this to
    exercise the participant-only path."""
    return AuthenticatedUser(
        principal_id="carol-oid",
        email="carol@example.edu",
        name="Carol",
        provider="aad",
    )


def _alice_session(client: TestClient, db: Session, code: str) -> ReviewSession:
    """Alice (workspace operator, default ``client`` user) creates
    a session — that registers her as the SessionOperator owner."""
    response = client.post(
        "/operator/sessions",
        data={"name": "S", "code": code, "description": ""},
        follow_redirects=False,
    )
    assert response.status_code == 303
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


# ── Workspace gate: participants without operator allowlist ──────────


def test_participant_only_user_redirected_from_operator_lobby(
    client: TestClient, db: Session, auth_carol: AuthenticatedUser
) -> None:
    """Carol is added to all three rosters on Alice's session.
    She holds no SessionOperator row and isn't on the operator /
    sys-admin allowlist. Hitting ``/operator/sessions``
    redirects her to ``/request-access`` — participant rosters
    don't open the operator surface."""
    review_session = _alice_session(client, db, "gate-1")
    db.add_all(
        [
            Reviewer(
                session_id=review_session.id,
                name="Carol",
                email="carol@example.edu",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Carol",
                email_or_identifier="carol@example.edu",
            ),
            Observer(
                session_id=review_session.id,
                email="carol@example.edu",
                display_name="Carol",
            ),
        ]
    )
    db.commit()

    carol_client = _make_client(db, auth_carol)
    response = carol_client.get("/operator/sessions")
    assert response.status_code == 303
    assert response.headers["location"] == "/request-access"


def test_participant_only_user_redirected_from_per_session_route(
    client: TestClient, db: Session, auth_carol: AuthenticatedUser
) -> None:
    """Workspace gate fires before the per-session check, so
    deep links to a specific session also bounce to
    ``/request-access`` for a non-operator participant."""
    review_session = _alice_session(client, db, "gate-2")
    db.add(
        Reviewer(
            session_id=review_session.id,
            name="Carol",
            email="carol@example.edu",
        )
    )
    db.commit()

    carol_client = _make_client(db, auth_carol)
    response = carol_client.get(
        f"/operator/sessions/{review_session.id}"
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/request-access"


# ── Per-session gate: workspace operator on someone else's session ───


def test_workspace_operator_non_owner_403_on_per_session_route(
    client: TestClient,
    db: Session,
    make_client,
    bob: AuthenticatedUser,
) -> None:
    """Bob is on the workspace operator allowlist (seeded by the
    integration conftest) but is not a SessionOperator on
    Alice's session — even though Alice added him to every
    roster. Per-session routes 403 him."""
    review_session = _alice_session(client, db, "gate-3")
    db.add_all(
        [
            Reviewer(
                session_id=review_session.id,
                name="Bob",
                email="bob@example.edu",
            ),
            Reviewee(
                session_id=review_session.id,
                name="Bob",
                email_or_identifier="bob@example.edu",
            ),
            Observer(
                session_id=review_session.id,
                email="bob@example.edu",
                display_name="Bob",
            ),
        ]
    )
    db.commit()

    bob_client = make_client(bob)
    response = bob_client.get(
        f"/operator/sessions/{review_session.id}",
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_workspace_operator_non_owner_lobby_excludes_others_sessions(
    client: TestClient,
    db: Session,
    make_client,
    bob: AuthenticatedUser,
) -> None:
    """Bob's lobby lists only the sessions where he holds the
    SessionOperator owner row, even if he's been added to
    Alice's session as a participant."""
    alice_session = _alice_session(client, db, "gate-4-alice")
    db.add(
        Reviewer(
            session_id=alice_session.id,
            name="Bob",
            email="bob@example.edu",
        )
    )
    db.commit()

    bob_client = make_client(bob)
    body = bob_client.get("/operator/sessions").text
    # Alice's session must not appear in Bob's lobby — he's only
    # a participant on it.
    assert "gate-4-alice" not in body


# ── Owner / sys-admin: positive control ──────────────────────────────


def test_session_owner_reaches_per_session_route(
    client: TestClient, db: Session
) -> None:
    """Alice (the SessionOperator owner) reaches her own
    session's per-session page — the positive control for the
    gate."""
    review_session = _alice_session(client, db, "gate-5")
    response = client.get(
        f"/operator/sessions/{review_session.id}",
        follow_redirects=False,
    )
    assert response.status_code == 200


def test_sys_admin_reaches_other_owners_per_session_route(
    client: TestClient,
    db: Session,
    make_client,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A sys-admin (here: dave) reaches Alice's session via the
    sys-admin relaxation — they bypass SessionOperator
    membership."""
    review_session = _alice_session(client, db, "gate-6")
    # Make sure Alice's session row carries an extract / outbox
    # surface a sys-admin would land on; we hit the audit-log
    # CSV which mounts ``require_sys_admin_or_session_operator``.
    monkeypatch.setattr(
        settings, "sys_admin_emails", ["dave@example.edu"]
    )
    monkeypatch.setattr(
        settings, "operator_emails", ["dave@example.edu"]
    )
    auth_dave = AuthenticatedUser(
        principal_id="dave-oid",
        email="dave@example.edu",
        name="Dave",
        provider="aad",
    )
    dave_client = make_client(auth_dave)
    response = dave_client.get(
        f"/operator/sessions/{review_session.id}/audit-log.csv",
        follow_redirects=False,
    )
    # 200 (success) or any non-403 — the sys-admin gate let
    # them through, that's the contract.
    assert response.status_code != 403
