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
    # The directory's display name, so the row reads as its person (19Z,
    # invite from the directory, rung 19).
    assert row.display_name == "Jane Tan"
    event = db.execute(select(AuditEvent).where(AuditEvent.event_type == "workspace.user_invited")).scalar_one()
    assert event.detail["snapshot"]["directory_verified"] is True
    assert event.detail["snapshot"]["display_name"] == "Jane Tan"


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
    assert row.display_name is None  # nothing to take a name from
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


def test_a_lookup_error_creates_the_row_unbound(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch, directory: None
) -> None:
    """An ERROR outcome (the fake directory's throttled address) never refuses."""
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    response = _invite(client, "throttled@example.edu")
    row = _row(db, "throttled@example.edu")
    assert row is not None and row.external_principal_id is None
    assert response.headers["location"].endswith("invite_unchecked=1")


def test_the_audit_records_the_object_id_bound(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch, directory: None
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    _invite(client, "jane.tan@example.edu")
    event = db.execute(select(AuditEvent).where(AuditEvent.event_type == "workspace.user_invited")).scalar_one()
    assert event.detail["snapshot"]["external_principal_id"] == JANE


def test_the_object_id_is_matched_in_any_case(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    """21F's rule: an Entra GUID may arrive in either case. An invite binds
    it folded; an account already holding it in another case is the same
    person; sign-in finds the row whichever case the header carries."""
    from cordware.graph import DirectoryUser, FakeDirectory

    from app.auth.identity import AuthenticatedUser
    from app.services import users
    from app.services.directory_accounts import look_up_one

    upper = JANE.upper()
    shouting = FakeDirectory((DirectoryUser(upper, "Jane Tan", "jane.tan@example.edu", "e0123456@example.edu"),))
    actor = User(email="alice@example.edu", is_operator=True, is_sys_admin=True)
    db.add(actor)
    db.commit()
    invited = users.invite(db, actor=actor, email="jane.tan@example.edu",
                           directory=lambda: look_up_one(shouting, "jane.tan@example.edu"))
    assert invited.external_principal_id == JANE  # folded
    with pytest.raises(users.UserOperationError) as refused:
        users.invite(db, actor=actor, email="e0123456@example.edu",
                     directory=lambda: look_up_one(shouting, "e0123456@example.edu"))
    assert refused.value.code == "account_exists"
    found = users.find_signed_in_user(db, AuthenticatedUser(principal_id=upper, email="jane.tan@example.edu", name="Jane"))
    assert found is not None and found.id == invited.id


def test_the_cheap_refusals_come_before_the_lookup(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch, directory: None
) -> None:
    """A duplicate is refused without asking the directory, and a plain
    admin's sys-admin invite says why before any lookup."""
    from app.services import directory_accounts

    asked: list[str] = []
    real = directory_accounts.look_up_one
    monkeypatch.setattr(directory_accounts, "look_up_one", lambda d, a: asked.append(a) or real(d, a))
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    _invite(client, "jane.tan@example.edu")
    assert _invite(client, "jane.tan@example.edu").headers["location"].endswith("invite_error=duplicate")
    assert asked == ["jane.tan@example.edu"]  # once, for the first invite


def test_the_fake_sign_in_s_id_is_no_one_s(db: Session) -> None:
    from cordware.settings import identity_settings

    from app.services.users import is_verified

    assert not is_verified(User(email="dev@example.edu", external_principal_id=identity_settings.fake_auth_principal_id))
    assert not is_verified(User(email="dev@example.edu", external_principal_id="  "))
    assert is_verified(User(email="dev@example.edu", external_principal_id=JANE))


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Jane Tan <jane.tan@example.edu>", ("Jane Tan", "jane.tan@example.edu")),
        ("  <jane.tan@example.edu> ", (None, "jane.tan@example.edu")),
        ("jane.tan@example.edu", (None, "jane.tan@example.edu")),
        ("Tan, Jane <a@b.edu> extra", (None, "Tan, Jane <a@b.edu> extra")),
    ],
)
def test_name_and_address_splits_only_the_picker_s_form(text: str, expected: tuple) -> None:
    from app.services.users import split_named_address

    assert split_named_address(text) == expected


def test_a_picked_name_and_address_invites_the_address(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch, directory: None
) -> None:
    """The picker fills "Name <address>"; the directory's name wins."""
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    response = _invite(client, "Jay T <jane.tan@example.edu>")
    row = _row(db, "jane.tan@example.edu")
    assert response.status_code == 303 and row is not None
    assert row.external_principal_id == JANE and row.display_name == "Jane Tan"


def test_an_unbound_picked_invite_keeps_the_picked_name(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    _invite(client, "New Person <new@example.edu>")  # no directory: nothing asked
    row = _row(db, "new@example.edu")
    assert row is not None and row.external_principal_id is None and row.display_name == "New Person"


@pytest.mark.parametrize(
    "text",
    ["Tan, Jane <a@b.edu> extra", "Jane Tan <jane.tan@example.edu", "not an address @ all"],
)
def test_text_that_is_not_one_address_is_refused_not_invited_unchecked(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch, directory: None, text: str
) -> None:
    """The box is a text box now, so anything but one whole address is
    refused rather than skipping the directory check (diff-reviewer)."""
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    response = _invite(client, text)
    assert response.headers["location"].endswith("invite_error=invalid_email")
    assert db.execute(select(User).where(User.email.contains("@"), User.email != "alice@example.edu")).first() is None


def test_a_picked_name_is_kept_to_the_column_s_length(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _bootstrap_sys_admin(monkeypatch, email="alice@example.edu")
    _invite(client, "N" * 300 + " <long@example.edu>")
    row = _row(db, "long@example.edu")
    assert row is not None and len(row.display_name) == 255
