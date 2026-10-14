"""Sys Admin → Accounts: the row expander's actions on several rows at
once (guide/admin_pages_refine.md Item 2). All or nothing: one refusal
refuses the batch, names the row and the reason, and changes nothing.
The guards that count across rows (``last_admin``, ``sole_owner``) judge
the state after the batch.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import AuditEvent, ReviewSession, SessionOperator, User
from app.services import users as users_service
from app.web import views

ACCOUNTS = "/operator/sys-admin/users"


@pytest.fixture
def actor(db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> User:
    """Alice, a super-admin, so every action is open to her; the first
    request creates her row."""
    monkeypatch.setattr(settings, "super_admin_emails", ["alice@example.edu"])
    client.get(ACCOUNTS)
    return db.execute(
        select(User).where(User.email == "alice@example.edu")
    ).scalar_one()


def _seed(db: Session, email: str, **flags: bool) -> User:
    user = User(email=email, **flags)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _session(db: Session, code: str, *owners: User) -> ReviewSession:
    review_session = ReviewSession(
        name=f"Session {code}", code=code, created_by_user_id=owners[0].id
    )
    db.add(review_session)
    db.flush()
    for owner in owners:
        db.add(SessionOperator(session_id=review_session.id, user_id=owner.id, role="owner"))
    db.commit()
    return review_session


def _post(client: TestClient, action: str, *users: User, **extra: str):
    return client.post(
        f"{ACCOUNTS}/bulk-{action}",
        data={"user_ids": [str(u.id) for u in users], **extra},
        follow_redirects=False,
    )


def _query(response) -> dict[str, list[str]]:
    return parse_qs(urlsplit(response.headers["location"]).query)


# --- Applied together --------------------------------------------------------


def test_revoking_two_operators_is_one_request_and_one_correlation(
    db: Session, client: TestClient, actor: User
) -> None:
    bob = _seed(db, "bob@example.edu", is_operator=True)
    carl = _seed(db, "carl@example.edu", is_operator=True)
    response = _post(client, "revoke", bob, carl, view="show=operators")
    assert response.status_code == 303
    assert _query(response) == {"show": ["operators"]}
    db.expire_all()
    assert (bob.is_operator, carl.is_operator) == (False, False)
    events = db.execute(
        select(AuditEvent).where(AuditEvent.event_type == "workspace.operator_revoked")
    ).scalars().all()
    assert sorted(e.detail["refs"]["target_user_id"] for e in events) == sorted(
        [bob.id, carl.id]
    )
    assert len({e.correlation_id for e in events}) == 1


def test_admit_promote_and_demote_apply_to_every_row(
    db: Session, client: TestClient, actor: User
) -> None:
    dave = _seed(db, "dave@example.edu")
    erin = _seed(db, "erin@example.edu")
    assert _post(client, "admit", dave, erin).status_code == 303
    assert _post(client, "promote", dave, erin).status_code == 303
    db.expire_all()
    assert all(u.is_operator and u.is_sys_admin for u in (dave, erin))
    assert _post(client, "demote", dave, erin).status_code == 303
    db.expire_all()
    assert not dave.is_sys_admin and not erin.is_sys_admin


def test_one_row_lands_on_its_row_several_do_not(
    db: Session, client: TestClient, actor: User
) -> None:
    dave = _seed(db, "dave@example.edu")
    erin = _seed(db, "erin@example.edu")
    assert _query(_post(client, "admit", dave))["selected"] == [str(dave.id)]
    assert "selected" not in _query(_post(client, "admit", dave, erin))


def test_deleting_unused_accounts_needs_the_confirm(
    db: Session, client: TestClient, actor: User
) -> None:
    dave = _seed(db, "dave@example.edu")
    erin = _seed(db, "erin@example.edu")
    assert _post(client, "delete", dave, erin).status_code == 400
    response = _post(client, "delete", dave, erin, confirm="true")
    assert response.status_code == 303
    assert "selected" not in _query(response)
    db.expire_all()
    assert db.execute(
        select(User).where(User.id.in_([dave.id, erin.id]))
    ).first() is None


# --- Refused whole -----------------------------------------------------------


def test_a_mixed_delete_is_refused_whole_naming_the_row(
    db: Session, client: TestClient, actor: User
) -> None:
    """The refused row is the one with history; the unused one stays too."""
    unused = _seed(db, "unused@example.edu")
    busy = _seed(db, "busy@example.edu")
    db.add(AuditEvent(event_type="response.submitted", summary="x", actor_user_id=busy.id, detail={}))
    db.commit()
    response = _post(client, "delete", unused, busy, confirm="true", view="show=unused&show=no_role")
    assert response.status_code == 303
    query = _query(response)
    assert query["toggle_error"] == ["has_history"]
    assert query["refused"] == [str(busy.id)]
    assert query["show"] == ["no_role", "unused"]
    db.expire_all()
    assert db.get(User, unused.id) is not None
    assert db.get(User, busy.id) is not None

    banner = client.get(response.headers["location"]).text
    assert "Nothing changed: busy@example.edu has created a session" in banner


def test_revoking_an_owner_refuses_the_batch(
    db: Session, client: TestClient, actor: User
) -> None:
    bob = _seed(db, "bob@example.edu", is_operator=True)
    owner = _seed(db, "owner@example.edu", is_operator=True)
    _session(db, "s1", owner, actor)
    query = _query(_post(client, "revoke", bob, owner))
    assert (query["toggle_error"], query["refused"]) == (["still_owner"], [str(owner.id)])
    db.expire_all()
    assert bob.is_operator and owner.is_operator


def test_promote_refuses_a_row_with_no_role(
    db: Session, client: TestClient, actor: User
) -> None:
    bob = _seed(db, "bob@example.edu", is_operator=True)
    dave = _seed(db, "dave@example.edu")
    query = _query(_post(client, "promote", bob, dave))
    assert (query["toggle_error"], query["refused"]) == (["not_operator"], [str(dave.id)])
    db.expire_all()
    assert not bob.is_sys_admin


def test_a_super_admin_target_is_refused(
    db: Session, client: TestClient, actor: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        settings, "super_admin_emails", ["alice@example.edu", "boss@example.edu"]
    )
    boss = _seed(db, "boss@example.edu", is_operator=True, is_sys_admin=True)
    query = _query(_post(client, "demote", boss))
    assert query["toggle_error"] == ["protected_super_admin"]


# --- Set-level guards judge the state after the batch -----------------------


def test_two_admins_demoted_together_are_refused_by_last_admin(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each alone would leave the other; together they'd leave none. The
    actor is a super-admin by config whose row carries no admin flag."""
    monkeypatch.setattr(settings, "super_admin_emails", ["boss@example.edu"])
    boss = _seed(db, "boss@example.edu", is_operator=True)
    ann = _seed(db, "ann@example.edu", is_operator=True, is_sys_admin=True)
    ben = _seed(db, "ben@example.edu", is_operator=True, is_sys_admin=True)
    with pytest.raises(users_service.UserOperationError) as refused:
        users_service.apply_batch(db, actor=boss, action="demote", user_ids=[ann.id, ben.id])
    assert refused.value.code == "last_admin"
    assert refused.value.user_id == ann.id
    db.rollback()
    db.expire_all()
    assert ann.is_sys_admin and ben.is_sys_admin
    # One of them alone is fine.
    users_service.apply_batch(db, actor=boss, action="demote", user_ids=[ben.id])
    db.expire_all()
    assert ann.is_sys_admin and not ben.is_sys_admin


def test_two_co_owners_removed_together_are_refused_by_sole_owner(
    db: Session, client: TestClient, actor: User
) -> None:
    ann = _seed(db, "ann@example.edu", is_operator=True)
    ben = _seed(db, "ben@example.edu", is_operator=True)
    shared = _session(db, "shared", ann, ben)
    _session(db, "ann-and-alice", ann, actor)
    query = _query(_post(client, "remove-from-all-sessions", ann, ben))
    assert (query["toggle_error"], query["refused"]) == (["sole_owner"], [str(ann.id)])
    owners = db.execute(
        select(SessionOperator.user_id).where(SessionOperator.session_id == shared.id)
    ).scalars().all()
    assert sorted(owners) == sorted([ann.id, ben.id])
    # Ann alone leaves Ben on the shared one and Alice on the other.
    assert _post(client, "remove-from-all-sessions", ann).status_code == 303
    assert db.execute(
        select(SessionOperator).where(SessionOperator.user_id == ann.id)
    ).first() is None


# --- The route's own refusals -----------------------------------------------


def test_the_route_refuses_what_no_selection_should_send(
    db: Session, client: TestClient, actor: User
) -> None:
    bob = _seed(db, "bob@example.edu", is_operator=True)
    assert _post(client, "admit").status_code == 400  # nothing selected
    assert _post(client, "admit", actor).status_code == 400  # your own row
    assert _post(client, "reboot", bob).status_code == 404  # no such action
    response = client.post(
        f"{ACCOUNTS}/bulk-admit", data={"user_ids": ["999999"]}, follow_redirects=False
    )
    assert response.status_code == 404


def test_a_plain_admin_cannot_promote_while_a_super_tier_exists(
    db: Session, client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    monkeypatch.setattr(settings, "super_admin_emails", ["boss@example.edu"])
    client.get(ACCOUNTS)
    bob = _seed(db, "bob@example.edu", is_operator=True)
    assert _post(client, "promote", bob).status_code == 403


# --- The banner names the row from the page's own words ---------------------


def test_the_banner_reason_comes_from_the_view_not_the_url() -> None:
    assert views.account_refusal_message("still_owner", "bob@example.edu") == (
        "Nothing changed: bob@example.edu still owns sessions; remove them "
        "from all sessions first."
    )
    assert views.account_refusal_message("last_admin", None) == (
        "Nothing changed: that would leave the workspace with no sys-admin."
    )
    # An unknown code, or a row-naming reason with no row, gets a fixed
    # sentence: the code is the URL's, so it never reaches the page.
    assert views.account_refusal_message(
        "Your account was suspended, re-verify at evil.example", None
    ) == "Couldn't apply that change."
    assert views.account_refusal_message("has_history", None) == (
        "Couldn't apply that change."
    )
