"""An operator's Unit (segment 20D rung 5, `docs/header_chrome.md` §6):
set only by a system admin, audited, and shown as the top line by the
"Which name a page shows" table."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.identity import AuthenticatedUser
from app.config import settings
from app.db.models import AuditEvent, Reviewer, ReviewSession, User
from app.services import users as users_service
from cordware.settings import identity_settings

from ._lookups import detail_of

DEFAULT = "Example University"


@pytest.fixture(autouse=True)
def _default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "institution_name", DEFAULT)


def _top(body: str) -> str | None:
    marker = '<span class="tb-top">'
    if marker not in body:
        return None
    return body.split(marker, 1)[1].split("</span>", 1)[0]


def _user(db: Session, email: str) -> User:
    return db.execute(select(User).where(User.email == email)).scalar_one()


def _session(client: TestClient, db: Session, code: str) -> ReviewSession:
    client.post(
        "/operator/sessions",
        data={"name": f"Unit {code}", "code": code},
        follow_redirects=False,
    )
    return db.execute(select(ReviewSession).where(ReviewSession.code == code)).scalar_one()


def _set_unit(db: Session, email: str, unit: str | None) -> None:
    _user(db, email).unit = unit
    db.commit()


# -- the service ------------------------------------------------------


def _admin(db: Session) -> User:
    admin = User(email="admin@example.edu", is_operator=True, is_sys_admin=True)
    db.add(admin)
    db.commit()
    return admin


def _operator(db: Session, email: str = "op@example.edu") -> User:
    operator = User(email=email, is_operator=True)
    db.add(operator)
    db.commit()
    return operator


def test_set_unit_trims_stores_and_audits(db: Session) -> None:
    admin, operator = _admin(db), _operator(db)
    changed = users_service.set_unit(
        db, actor=admin, user_ids=[operator.id], unit="  Department   of Example "
    )
    assert changed == 1
    db.refresh(operator)
    assert operator.unit == "Department of Example"
    event = db.execute(
        select(AuditEvent)
        .where(AuditEvent.event_type == "workspace.user_unit_set")
        .order_by(AuditEvent.id)
    ).scalar_one()
    assert detail_of(event)["changes"] == {"unit": [None, "Department of Example"]}
    assert detail_of(event)["refs"] == {"target_user_id": operator.id}


def test_an_empty_value_clears_and_an_unchanged_one_is_not_audited(
    db: Session,
) -> None:
    admin, operator = _admin(db), _operator(db)
    users_service.set_unit(db, actor=admin, user_ids=[operator.id], unit="Dept")
    assert users_service.set_unit(db, actor=admin, user_ids=[operator.id], unit="Dept") == 0
    users_service.set_unit(db, actor=admin, user_ids=[operator.id], unit="   ")
    db.refresh(operator)
    assert operator.unit is None
    events = (
        db.execute(
            select(AuditEvent)
            .where(AuditEvent.event_type == "workspace.user_unit_set")
            .order_by(AuditEvent.id)
        )
        .scalars()
        .all()
    )
    assert [detail_of(e)["changes"]["unit"] for e in events] == [[None, "Dept"], ["Dept", None]]


def test_set_unit_refuses_a_row_with_no_role_and_changes_nothing(db: Session) -> None:
    admin, operator = _admin(db), _operator(db)
    stranger = User(email="nobody@example.edu")
    db.add(stranger)
    db.commit()
    with pytest.raises(users_service.UserOperationError) as exc:
        users_service.set_unit(db, actor=admin, user_ids=[operator.id, stranger.id], unit="Dept")
    assert exc.value.code == "unit_not_operator"
    assert exc.value.user_id == stranger.id
    db.rollback()
    db.refresh(operator)
    assert operator.unit is None


def test_set_unit_refuses_more_than_80_characters(db: Session) -> None:
    admin, operator = _admin(db), _operator(db)
    with pytest.raises(users_service.UserOperationError) as exc:
        users_service.set_unit(db, actor=admin, user_ids=[operator.id], unit="x" * 81)
    assert exc.value.code == "unit_too_long"
    users_service.set_unit(db, actor=admin, user_ids=[operator.id], unit="x" * 80)


# -- the route --------------------------------------------------------


def test_a_sys_admin_sets_a_unit_from_accounts_management(
    client: TestClient, db: Session, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    client.get("/operator/sessions")
    target = _operator(db, "bob@example.edu")
    response = client.post(
        "/operator/sys-admin/users/bulk-set-unit",
        data={"user_ids": [str(target.id)], "unit": "Department of Example"},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    db.refresh(target)
    assert target.unit == "Department of Example"
    body = client.get("/operator/sys-admin/users?show=operators&show=admins").text
    assert "<td data-unit-cell>Department of Example</td>" in body


def test_an_operator_cannot_set_a_unit(client: TestClient, db: Session) -> None:
    client.get("/operator/sessions")
    me = _user(db, "alice@example.edu")
    response = client.post(
        "/operator/sys-admin/users/bulk-set-unit",
        data={"user_ids": [str(me.id)], "unit": "Mine"},
        follow_redirects=False,
    )
    assert response.status_code in (303, 403)
    db.refresh(me)
    assert me.unit is None


def test_a_refusal_comes_back_naming_the_row(client: TestClient, db: Session, monkeypatch) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    client.get("/operator/sessions")
    stranger = User(email="nobody@example.edu")
    db.add(stranger)
    db.commit()
    response = client.post(
        "/operator/sys-admin/users/bulk-set-unit",
        data={"user_ids": [str(stranger.id)], "unit": "Dept"},
    )
    assert "Nothing changed: nobody@example.edu has no role, so has no unit." in response.text


def test_settings_shows_the_operators_own_unit(client: TestClient, db: Session) -> None:
    client.get("/operator/sessions")
    _set_unit(db, "alice@example.edu", "Department of Example")
    body = client.get("/operator/settings").text
    assert "Your unit:\n      <strong>Department of Example</strong>" in body


# -- which name a page shows ------------------------------------------


def test_an_operators_other_pages_show_their_own_unit(client: TestClient, db: Session) -> None:
    assert _top(client.get("/operator/sessions").text) == DEFAULT
    _set_unit(db, "alice@example.edu", "Department of Example")
    for path in (
        "/operator/sessions",
        "/operator/settings",
        "/about",
        "/guide",
        "/auth/me/debug",
    ):
        assert _top(client.get(path).text) == "Department of Example", path


def test_a_session_shows_its_creators_unit_to_co_owners(
    client: TestClient, db: Session, make_client, bob
) -> None:
    # One client identity at a time: ``make_client`` swaps the app's.
    review_session = _session(client, db, "unit-co")
    _operator(db, "bob@example.edu")
    added = client.post(
        f"/operator/sessions/{review_session.public_id}/owners/add",
        data={"target_email": "bob@example.edu"},
        follow_redirects=False,
    )
    assert "owners_error" not in added.headers["location"]
    bob_client = make_client(bob)
    _set_unit(db, "alice@example.edu", "Creator Dept")
    _set_unit(db, "bob@example.edu", "Co-owner Dept")
    home = f"/operator/sessions/{review_session.public_id}"
    assert _top(bob_client.get(home).text) == "Creator Dept"
    # The co-owner's own pages keep their own Unit.
    assert _top(bob_client.get("/operator/sessions").text) == "Co-owner Dept"
    # A creator with no Unit shows the default, whatever a co-owner holds.
    _set_unit(db, "alice@example.edu", None)
    assert _top(bob_client.get(home).text) == DEFAULT


def test_participants_see_the_creators_unit_and_the_default_elsewhere(
    client: TestClient, db: Session, make_client
) -> None:
    review_session = _session(client, db, "unit-pt")
    db.add(Reviewer(session_id=review_session.id, name="Pat", email="pat@example.edu"))
    db.commit()
    _set_unit(db, "alice@example.edu", "Creator Dept")
    pat = make_client(
        AuthenticatedUser(
            principal_id="pat-oid",
            email="pat@example.edu",
            name="Pat",
            provider="aad",
        )
    )
    page = pat.get(f"/me/sessions/{review_session.public_id}").text
    assert _top(page) == "Creator Dept"
    # Your reviews: every listed session resolves to the same Unit.
    assert _top(pat.get("/me").text) == "Creator Dept"
    # About and Guide: the default for a participant.
    assert _top(pat.get("/about").text) == DEFAULT


def test_your_reviews_shows_the_default_when_sessions_differ(
    client: TestClient, db: Session, make_client, bob
) -> None:
    first = _session(client, db, "unit-a")
    second = _session(make_client(bob), db, "unit-b")
    for review_session in (first, second):
        db.add(Reviewer(session_id=review_session.id, name="Pat", email="pat@example.edu"))
    db.commit()
    _set_unit(db, "alice@example.edu", "Dept A")
    _set_unit(db, "bob@example.edu", "Dept B")
    pat = make_client(
        AuthenticatedUser(
            principal_id="pat-oid",
            email="pat@example.edu",
            name="Pat",
            provider="aad",
        )
    )
    assert _top(pat.get("/me").text) == DEFAULT


def test_sign_in_details_names_the_viewer_in_the_bar(client: TestClient) -> None:
    """The page renders the header identity; the bar shows the row
    (cold read of 20D): name, account label and Unit."""
    client.get("/operator/sessions")
    body = client.get("/auth/me/debug").text
    assert 'aria-label="Account: Alice Example"' in body
    assert "<strong>Alice Example</strong>" in body


def test_an_account_with_no_role_has_a_blank_unit_cell(
    client: TestClient, db: Session, monkeypatch
) -> None:
    """Plan Semantics: non-operators' cells are blank, even with a Unit
    kept from when they were one."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    client.get("/operator/sessions")
    former = User(email="former@example.edu", unit="Old Dept")
    db.add(former)
    db.commit()
    body = client.get("/operator/sys-admin/users?show=no_role&show=unused&q=former").text
    assert "former@example.edu" in body
    assert "<td data-unit-cell></td>" in body
    assert "Old Dept" not in body


@pytest.mark.parametrize("child", ["outbox", "audit-log"])
def test_sys_admin_session_diagnostics_show_the_creators_unit(
    client: TestClient, db: Session, monkeypatch, child: str
) -> None:
    """Codex on #3509: these pass the session under their own keys."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    review_session = _session(client, db, f"unit-diag-{child}")
    _set_unit(db, "alice@example.edu", "Admin Dept")
    creator = _user(db, "alice@example.edu")
    other = _operator(db, "creator@example.edu")
    review_session.created_by_user_id = other.id
    other.unit = "Creator Dept"
    db.commit()
    assert creator.unit == "Admin Dept"
    body = client.get(f"/operator/sys-admin/sessions/{review_session.public_id}/{child}").text
    assert _top(body) == "Creator Dept"
