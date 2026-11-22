"""Admins (segment AD2M, rung 3; `applydesk/spec/permissions.md` §2): the
super-admin promotes and demotes them; an Admin reaches the Admin pages and
keeps the operator list, but cannot make Admins; an Admin is demoted before
being taken off the list; with no super-admin configured, the last Admin
stays one."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from applydesk import db, operators, people, seed
from applydesk.models import AuditEvent, Person
from applydesk.operators import Actor, Refused
from applydesk.tests._host import host_with
from cordware.identity import Identity
from cordware.settings import identity_settings

SUPER = Actor(None, is_super_admin=True)


def _signed_in(email: str, oid: str, name: str = "Ben Ong") -> int:
    session = db.new_session()
    person = people.resolve(
        session, Identity(principal_id=oid, email=email, name=name, tenant_id="local-tenant")
    )
    assert person is not None
    session.commit()
    pid = person.id
    session.close()
    return pid


def _person(pid: int) -> Person:
    session = db.new_session()
    try:
        found = session.get(Person, pid)
        assert found is not None
        return found
    finally:
        session.close()


def _events() -> list[str]:
    session = db.new_session()
    try:
        return [e.event_type for e in session.scalars(select(AuditEvent).order_by(AuditEvent.id))]
    finally:
        session.close()


def _as(pid: int, change: str) -> None:
    session = db.new_session()
    person = session.get(Person, pid)
    assert person is not None
    getattr(operators, change)(session, SUPER, person)
    session.commit()
    session.close()


def test_the_super_admin_promotes_and_demotes_from_the_bulk_bar() -> None:
    admin = TestClient(host_with(("applydesk",))[0])
    ben = _signed_in("ben@example.edu", "o-ben")
    page = admin.get("/applydesk/admin/operators").text
    assert 'value="promote" disabled data-bulk-action data-bulk-promote>Promote to Admin' in page
    made = admin.post(
        "/applydesk/admin/operators/bulk",
        data={"action": "promote", "person_ids": str(ben)},
        follow_redirects=False,
    )
    assert "done=promote" in made.headers["location"] and "n=1" in made.headers["location"]
    promoted = _person(ben)
    assert promoted.is_admin and operators.may_operate(promoted)  # Promote lists them too
    assert _events()[-2:] == ["person.admitted", "person.promoted"]
    shown = admin.get("/applydesk/admin/operators?show=admins").text
    row = shown[shown.index(f'data-op-entry="{ben}"') :]
    assert '<span class="chip chip-info">Admin</span>' in row[: row.index("</tr>")]
    assert "Made Admins: 1." in admin.get(made.headers["location"]).text
    # Revoke refuses an Admin: demote first.
    refused = admin.post(
        "/applydesk/admin/operators/bulk",
        data={"action": "revoke", "person_ids": str(ben)},
        follow_redirects=False,
    )
    assert "n=0" in refused.headers["location"] and "skipped=1" in refused.headers["location"]
    admin.post("/applydesk/admin/operators/bulk", data={"action": "demote", "person_ids": str(ben)})
    demoted = _person(ben)
    assert not demoted.is_admin and operators.may_operate(demoted)
    assert _events()[-1] == "person.demoted"


def test_a_pending_person_cannot_be_promoted() -> None:
    session = db.new_session()
    pat = people.pending(session, "pat@example.edu", None)
    session.commit()
    with pytest.raises(Refused) as refused:
        operators.promote(session, SUPER, pat)
    assert refused.value.key == "pending"
    session.close()


def test_an_admin_keeps_the_list_but_cannot_make_admins(monkeypatch: pytest.MonkeyPatch) -> None:
    """The fake identity, made an Admin and not the super-admin, reaches the
    Admin pages and admits; Promote is not offered and is refused."""
    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", False)
    monkeypatch.setattr(identity_settings, "super_admin_emails", ["root@example.edu"])
    session = db.new_session()
    seed.seed(session)  # the fake identity, bound and on the list
    me = session.scalar(select(Person).where(Person.object_id == "local-dev"))
    assert me is not None
    me_id = me.id
    session.close()
    client = TestClient(host_with(("applydesk",))[0])
    assert client.get("/applydesk/admin/operators").status_code == 404  # an operator only
    _as(me_id, "promote")
    page = client.get("/applydesk/admin/operators").text
    assert "<h1>Admin</h1>" in page and "data-bulk-promote" not in page
    assert "<span>admin</span>" in page  # the account menu names an Admin
    assert client.get("/applydesk/admin/exercises").status_code == 200
    ed = _signed_in("ed@example.edu", "o-ed", "Ed Lim")
    admitted = client.post(
        "/applydesk/admin/operators/bulk",
        data={"action": "admit", "person_ids": str(ed)},
        follow_redirects=False,
    )
    assert "n=1" in admitted.headers["location"]
    forged = client.post(
        "/applydesk/admin/operators/bulk",
        data={"action": "promote", "person_ids": str(ed)},
        follow_redirects=False,
    )
    assert "n=0" in forged.headers["location"] and not _person(ed).is_admin
    # Their own row: Admin, and (self); not the super-admin's.
    own = page[page.index(f'data-op-entry="{me_id}"') :]
    own = own[: own.index("</tr>")]
    assert "(self)" in own and '<span class="chip chip-info">Admin</span>' in own
    assert "Super-admin" not in own


def test_with_no_super_admin_an_admin_makes_admins_but_not_the_last_away(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Review Robin's fallback: with none configured, any Admin promotes and
    demotes, and the last Admin stays one."""
    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", False)
    monkeypatch.setattr(identity_settings, "super_admin_emails", [])
    ann = _signed_in("ann@example.edu", "o-ann", "Ann Koh")
    ben = _signed_in("ben@example.edu", "o-ben")
    _as(ann, "promote")
    session = db.new_session()
    ann_actor = Actor(session.get(Person, ann))
    ben_row = session.get(Person, ben)
    assert ben_row is not None
    operators.promote(session, ann_actor, ben_row)
    operators.demote(session, ann_actor, ben_row)
    ann_row = session.get(Person, ann)
    assert ann_row is not None
    with pytest.raises(Refused) as refused:
        operators.demote(session, ann_actor, ann_row)
    assert refused.value.key == "last_admin"
    session.close()


def test_an_operator_cannot_reach_the_admin_pages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", False)
    session = db.new_session()
    seed.seed(session)
    session.close()
    client = TestClient(host_with(("applydesk",))[0])
    for page in ("operators", "exercises", "system"):
        assert client.get(f"/applydesk/admin/{page}").status_code == 404
    assert (
        client.post(
            "/applydesk/admin/operators/bulk", data={"action": "promote", "person_ids": "1"}
        ).status_code
        == 404
    )
