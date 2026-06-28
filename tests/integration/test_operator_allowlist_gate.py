"""Coverage for the Segment 16A PR 1 operator-allowlist gate.

Exercises:
- First-sign-in bootstrap of ``users.is_operator`` /
  ``users.is_sys_admin`` from the ``OPERATOR_EMAILS`` /
  ``SYS_ADMIN_EMAILS`` env vars (F3).
- ``require_operator`` redirects non-operators to
  ``/request-access`` (F1).
- Sys-admin implies operator at the predicate level (F4).
- The ``/request-access`` landing page renders for the
  signed-in-but-not-allowlisted case (F5).
- ``FAKE_AUTH_OPERATOR`` / ``FAKE_AUTH_SYS_ADMIN`` shortcuts honour
  fake auth in dev / sandbox.

The gate itself isn't applied to every operator route until 16A
PR 1b; here we exercise the dependency in isolation via a
single test-only route mounted on the live FastAPI app.
"""
from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import APIRouter, Depends, Request
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser, get_current_user
from app.config import settings
from app.db.models import User
from app.db.session import get_db
from app.main import app
from app.web.deps import (
    OperatorAllowlistDenied,
    get_or_create_user,
    require_operator,
)


# --- Test-only route mounted on the live app to exercise require_operator -

_test_router = APIRouter()


@_test_router.get("/__test/operator-gated")
def _operator_gated(user: User = Depends(require_operator)) -> dict[str, object]:
    return {
        "email": user.email,
        "is_operator": user.is_operator,
        "is_sys_admin": user.is_sys_admin,
    }


@pytest.fixture(autouse=True)
def _mount_test_route() -> Iterator[None]:
    app.include_router(_test_router)
    try:
        yield
    finally:
        app.router.routes = [
            r
            for r in app.router.routes
            if getattr(r, "path", None) != "/__test/operator-gated"
        ]


# --- Helpers ----------------------------------------------------------------


def _make_client(
    db: Session,
    auth_user: AuthenticatedUser,
) -> TestClient:
    def override_get_db() -> Iterator[Session]:
        yield db

    def override_get_current_user() -> AuthenticatedUser:
        return auth_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def auth_alice() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="alice-oid",
        email="alice@example.edu",
        name="Alice",
        provider="aad",
    )


@pytest.fixture
def auth_bob() -> AuthenticatedUser:
    return AuthenticatedUser(
        principal_id="bob-oid",
        email="bob@example.edu",
        name="Bob",
        provider="aad",
    )


@pytest.fixture(autouse=True)
def _clear_overrides() -> Iterator[None]:
    try:
        yield
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _reset_allowlists(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "operator_emails", [])
    monkeypatch.setattr(settings, "sys_admin_emails", [])
    monkeypatch.setattr(settings, "fake_auth_operator", False)
    monkeypatch.setattr(settings, "fake_auth_sys_admin", False)
    monkeypatch.setattr(settings, "allow_fake_auth", False)


# --- Bootstrap on first sign-in (F3) ---------------------------------------


def test_first_sign_in_outside_allowlist_creates_user_with_both_flags_false(
    db: Session,
    auth_alice: AuthenticatedUser,
) -> None:
    client = _make_client(db, auth_alice)

    response = client.get("/__test/operator-gated")
    assert response.status_code == 303
    assert response.headers["location"] == "/request-access"

    user = db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()
    assert user.is_operator is False
    assert user.is_sys_admin is False


def test_operator_email_bootstrap_flips_is_operator_on_first_sign_in(
    db: Session,
    auth_alice: AuthenticatedUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "operator_emails", ["alice@example.edu"])
    client = _make_client(db, auth_alice)

    response = client.get("/__test/operator-gated")
    assert response.status_code == 200
    assert response.json() == {
        "email": "alice@example.edu",
        "is_operator": True,
        "is_sys_admin": False,
    }

    user = db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()
    assert user.is_operator is True
    assert user.is_sys_admin is False


def test_sys_admin_email_bootstrap_flips_is_sys_admin_on_first_sign_in(
    db: Session,
    auth_alice: AuthenticatedUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    client = _make_client(db, auth_alice)

    response = client.get("/__test/operator-gated")
    assert response.status_code == 200
    assert response.json() == {
        "email": "alice@example.edu",
        "is_operator": False,
        "is_sys_admin": True,
    }


def test_email_match_is_case_insensitive(
    db: Session,
    auth_alice: AuthenticatedUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "operator_emails", ["Alice@Example.EDU"])
    client = _make_client(db, auth_alice)

    response = client.get("/__test/operator-gated")
    assert response.status_code == 200


# --- Bootstrap runs once: env-var removal does NOT auto-revoke -------------


def test_bootstrap_runs_once_env_var_removal_does_not_auto_revoke(
    db: Session,
    auth_alice: AuthenticatedUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "operator_emails", ["alice@example.edu"])
    client = _make_client(db, auth_alice)

    # First sign-in writes ``is_operator=True``.
    response = client.get("/__test/operator-gated")
    assert response.status_code == 200

    # Operator's email is removed from the env var. The persisted
    # column is authoritative — they still pass the gate.
    monkeypatch.setattr(settings, "operator_emails", [])
    response = client.get("/__test/operator-gated")
    assert response.status_code == 200


# --- Sys-admin implies operator (F4) ---------------------------------------


def test_sys_admin_without_operator_flag_still_passes_gate(
    db: Session,
    auth_alice: AuthenticatedUser,
) -> None:
    # Pre-seed a user row that's sys-admin only (no env-var bootstrap).
    user = User(
        email="alice@example.edu",
        display_name="Alice",
        is_operator=False,
        is_sys_admin=True,
    )
    db.add(user)
    db.commit()

    client = _make_client(db, auth_alice)
    response = client.get("/__test/operator-gated")
    assert response.status_code == 200
    assert response.json()["is_operator"] is False
    assert response.json()["is_sys_admin"] is True


# --- Revocation: previously admitted operator loses access -----------------


def test_revoked_operator_is_redirected(
    db: Session,
    auth_bob: AuthenticatedUser,
) -> None:
    user = User(
        email="bob@example.edu",
        display_name="Bob",
        is_operator=False,
        is_sys_admin=False,
    )
    db.add(user)
    db.commit()

    client = _make_client(db, auth_bob)
    response = client.get("/__test/operator-gated")
    assert response.status_code == 303
    assert response.headers["location"] == "/request-access"


# --- Fake-auth toggle (F3, sandbox) ----------------------------------------


def test_fake_auth_operator_toggle_grants_operator_on_first_sign_in(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "allow_fake_auth", True)
    monkeypatch.setattr(settings, "fake_auth_operator", True)
    fake_user = AuthenticatedUser(
        principal_id="fake-oid",
        email="fake-op@example.edu",
        name="Fake Op",
        provider="fake",
        is_fake=True,
    )
    client = _make_client(db, fake_user)

    response = client.get("/__test/operator-gated")
    assert response.status_code == 200
    user = db.execute(
        select(User).where(User.email == "fake-op@example.edu")
    ).scalar_one()
    assert user.is_operator is True
    assert user.is_sys_admin is False


def test_fake_auth_sys_admin_toggle_grants_sys_admin_on_first_sign_in(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "allow_fake_auth", True)
    monkeypatch.setattr(settings, "fake_auth_sys_admin", True)
    fake_user = AuthenticatedUser(
        principal_id="fake-oid",
        email="fake-admin@example.edu",
        name="Fake Admin",
        provider="fake",
        is_fake=True,
    )
    client = _make_client(db, fake_user)

    response = client.get("/__test/operator-gated")
    assert response.status_code == 200
    user = db.execute(
        select(User).where(User.email == "fake-admin@example.edu")
    ).scalar_one()
    assert user.is_sys_admin is True


def test_fake_auth_toggle_is_inert_when_user_is_not_fake(
    db: Session,
    auth_alice: AuthenticatedUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real Easy-Auth principal should never inherit the sandbox
    operator flag even if the env var is set; the toggle only
    applies when ``is_fake`` is true on the resolved identity."""
    monkeypatch.setattr(settings, "allow_fake_auth", True)
    monkeypatch.setattr(settings, "fake_auth_operator", True)
    client = _make_client(db, auth_alice)

    response = client.get("/__test/operator-gated")
    assert response.status_code == 303


# --- Gate is mounted on the operator router (PR 1b) ------------------------


def test_operator_lobby_redirects_unallowlisted_user(
    db: Session,
) -> None:
    """Regression cover for PR 1b: the ``require_operator`` dependency
    is mounted on the parent operator ``APIRouter`` so every route
    under ``/operator/*`` gates uniformly. A signed-in but not-
    allowlisted user hitting the lobby (the lightest-weight operator
    route) gets bounced to ``/request-access`` — not 200, not 403."""
    intruder = AuthenticatedUser(
        principal_id="intruder-oid",
        email="intruder@example.edu",
        name="Intruder",
        provider="aad",
    )
    client = _make_client(db, intruder)
    response = client.get("/operator/sessions")
    assert response.status_code == 303
    assert response.headers["location"] == "/request-access"


def test_operator_lobby_reachable_for_allowlisted_user(
    db: Session,
    auth_alice: AuthenticatedUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "operator_emails", ["alice@example.edu"])
    client = _make_client(db, auth_alice)
    response = client.get("/operator/sessions")
    assert response.status_code == 200


# --- /request-access landing page (F5) -------------------------------------


def test_request_access_page_renders_for_signed_in_user(
    db: Session,
    auth_alice: AuthenticatedUser,
) -> None:
    client = _make_client(db, auth_alice)
    response = client.get("/request-access")
    assert response.status_code == 200
    body = response.text
    assert "Request access" in body
    assert "alice@example.edu" in body
    # No contact email configured by default; mailto link absent.
    assert "mailto:" not in body


def test_request_access_page_renders_contact_mailto_when_configured(
    db: Session,
    auth_alice: AuthenticatedUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings, "operator_contact_email", "admin@example.edu"
    )
    client = _make_client(db, auth_alice)
    response = client.get("/request-access")
    assert response.status_code == 200
    assert "mailto:admin@example.edu" in response.text


# --- Direct dependency-level smoke test ------------------------------------


def test_require_operator_returns_user_on_hit(db: Session) -> None:
    user = User(
        email="op@example.edu",
        display_name="Op",
        is_operator=True,
        is_sys_admin=False,
    )
    db.add(user)
    db.commit()

    returned = require_operator(user=user)
    assert returned is user


def test_require_operator_raises_on_miss(db: Session) -> None:
    user = User(
        email="nobody@example.edu",
        display_name="Nobody",
        is_operator=False,
        is_sys_admin=False,
    )
    with pytest.raises(OperatorAllowlistDenied):
        require_operator(user=user)


def test_get_or_create_user_reuses_existing_row_without_reapplying_bootstrap(
    db: Session,
    auth_alice: AuthenticatedUser,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If a row already exists with ``is_operator=False``, bootstrap
    must NOT promote on subsequent sign-ins even if the email is on
    the env-var allowlist (the env var is a first-sign-in seed only,
    per F3)."""
    user = User(
        email="alice@example.edu",
        display_name="Alice",
        is_operator=False,
        is_sys_admin=False,
    )
    db.add(user)
    db.commit()

    monkeypatch.setattr(settings, "operator_emails", ["alice@example.edu"])

    # Drive through the dependency to mimic a sign-in.
    returned = get_or_create_user(
        request=Request({"type": "http"}), current_user=auth_alice, db=db
    )
    assert returned.id == user.id
    assert returned.is_operator is False


def test_get_or_create_user_matches_existing_row_case_insensitively(
    db: Session,
) -> None:
    """A pre-seeded ``User`` row with a different-cased email must be
    reused on first sign-in instead of inserting a duplicate row.
    Slice A in ``guide/archive/weaknesses_and_bugs_found_by_codex.md``."""
    existing = User(
        email="Alice@example.edu",
        display_name="Alice",
        is_operator=False,
        is_sys_admin=False,
    )
    db.add(existing)
    db.commit()

    auth = AuthenticatedUser(
        principal_id="alice-oid",
        email="alice@example.edu",
        name="Alice",
        provider="aad",
    )
    returned = get_or_create_user(
        request=Request({"type": "http"}), current_user=auth, db=db
    )
    assert returned.id == existing.id
    assert (
        db.execute(select(User).where(User.email.ilike("alice@example.edu")))
        .scalars()
        .unique()
        .all()
        == [existing]
    )


def test_get_or_create_user_resolves_historical_case_variant_duplicates(
    db: Session,
) -> None:
    """Defense-in-depth for rows created before this normalization
    landed: if two ``User`` rows already exist whose emails differ
    only by case, the lookup must not raise ``MultipleResultsFound``
    and must return the older row deterministically."""
    older = User(
        email="Alice@example.edu",
        display_name="Alice (older)",
        is_operator=True,
        is_sys_admin=False,
    )
    db.add(older)
    db.flush()
    newer = User(
        email="alice@example.edu",
        display_name="Alice (newer)",
        is_operator=False,
        is_sys_admin=False,
    )
    db.add(newer)
    db.commit()

    auth = AuthenticatedUser(
        principal_id="alice-oid",
        email="ALICE@example.edu",
        name="Alice",
        provider="aad",
    )
    returned = get_or_create_user(
        request=Request({"type": "http"}), current_user=auth, db=db
    )
    assert returned.id == older.id


def test_get_or_create_user_matches_existing_row_reverse_casing(
    db: Session,
) -> None:
    """Symmetric: pre-seeded lower-case row must match an upper-case
    authenticated email."""
    existing = User(
        email="bob@example.edu",
        display_name="Bob",
        is_operator=False,
        is_sys_admin=False,
    )
    db.add(existing)
    db.commit()

    auth = AuthenticatedUser(
        principal_id="bob-oid",
        email="Bob@Example.Edu",
        name="Bob",
        provider="aad",
    )
    returned = get_or_create_user(
        request=Request({"type": "http"}), current_user=auth, db=db
    )
    assert returned.id == existing.id
