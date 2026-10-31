"""Accounts › Invite checks the address against the directory (segment
19Z, accounts item, author 2026-10-31): a match binds the person's Entra
object id, the id sign-in matches first; not found, ambiguous and a
person who already has an account are refused; a lookup that could not
run creates the row unbound, saying so."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, User
from app.web.routes_operator import _sys_admin

from .test_sys_admin_users import _bootstrap_sys_admin

JANE = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def directory(monkeypatch: pytest.MonkeyPatch) -> None:
    from cordware.graph import FakeDirectory

    monkeypatch.setattr(_sys_admin, "directory_or_none", lambda request: FakeDirectory())
    monkeypatch.setattr(_sys_admin, "is_local", lambda: False)  # a deployed run


def _invite(client: TestClient, email: str):
    return client.post("/operator/sys-admin/users/invite", data={"email": email}, follow_redirects=False)


def _row(db: Session, email: str) -> User | None:
    db.expire_all()
    return db.execute(select(User).where(User.email == email)).scalar_one_or_none()


@pytest.mark.parametrize("address", ["e0123456@example.edu", "jane.tan@example.edu"])
def test_a_match_binds_the_person_and_keeps_the_address(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch, directory: None, address: str
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    response = _invite(client, address)
    row = _row(db, address)
    assert response.status_code == 303 and "invite_unchecked" not in response.headers["location"]
    assert row is not None and row.external_principal_id == JANE
    event = db.execute(select(AuditEvent).where(AuditEvent.event_type == "workspace.user_invited")).scalar_one()
    assert event.detail["snapshot"]["directory_verified"] is True


@pytest.mark.parametrize(
    ("address", "code"),
    [("nobody@example.edu", "not_in_directory"), ("office@example.edu", "ambiguous_in_directory")],
)
def test_not_found_and_ambiguous_are_refused(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch, directory: None, address: str, code: str
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    response = _invite(client, address)
    assert response.headers["location"].endswith(f"invite_error={code}")
    assert _row(db, address) is None
    page = client.get(response.headers["location"]).text
    assert ("isn't in the institution's directory" if code == "not_in_directory" else "more than one directory account") in page


def test_a_person_who_already_has_an_account_is_refused(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch, directory: None
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    assert _invite(client, "jane.tan@example.edu").status_code == 303
    response = _invite(client, "e0123456@example.edu")  # Jane's sign-in name
    assert response.headers["location"].endswith("invite_error=account_exists")
    assert _row(db, "e0123456@example.edu") is None


def test_a_lookup_that_could_not_run_creates_the_row_unbound_and_says_so(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    response = _invite(client, "new@example.edu")  # no directory: nothing asked
    row = _row(db, "new@example.edu")
    assert row is not None and row.external_principal_id is None
    assert response.headers["location"].endswith("invite_unchecked=1")
    assert "couldn't be checked against the" in client.get(response.headers["location"]).text


def test_the_bound_invitee_signs_in_by_either_address(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch, directory: None
) -> None:
    """Invited by sign-in name, Jane signs in with her mail: the principal
    id finds the invited row, which takes the address she signed in with."""
    from app.auth.identity import AuthenticatedUser
    from app.services.users import find_signed_in_user

    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    _invite(client, "e0123456@example.edu")
    invited = _row(db, "e0123456@example.edu")
    found = find_signed_in_user(
        db, AuthenticatedUser(principal_id=JANE, email="jane.tan@example.edu", name="Jane Tan")
    )
    assert found is not None and found.id == invited.id


def test_a_local_run_checks_nothing(db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Its directory is the fake one, and its invitees are made up."""
    from cordware.graph import FakeDirectory

    monkeypatch.setattr(_sys_admin, "directory_or_none", lambda request: FakeDirectory())
    monkeypatch.setattr(_sys_admin, "is_local", lambda: True)
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    response = _invite(client, "made.up@example.edu")
    assert _row(db, "made.up@example.edu") is not None and response.headers["location"].endswith("invite_unchecked=1")
