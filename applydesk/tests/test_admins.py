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

SUPER = Actor(None, is_super_admin=True, platform=True)


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
    _as(_signed_in("ann@example.edu", "o-ann", "Ann Koh"), "promote")  # Ben is not the last
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


# --- Rung 4: adopting an exercise ---

EX = "wa9juxbc2t"


def _drop_my_grant(public_id: str) -> None:
    """Take the fake identity (seeded Owner of every sample) off one."""
    from applydesk.models import Exercise, ExerciseOperator

    session = db.new_session()
    exercise = session.scalar(select(Exercise).where(Exercise.public_id == public_id))
    assert exercise is not None
    for grant in session.scalars(
        select(ExerciseOperator).where(ExerciseOperator.exercise_id == exercise.id)
    ):
        session.delete(grant)
    session.commit()
    session.close()


def test_the_super_admin_adopts_before_working_on_an_exercise() -> None:
    """The author's ruling (2026-11-22): the super-admin reaches only what
    they own or operate; Manage adopts the rest as an Owner, audited."""
    client = TestClient(host_with(("applydesk",))[0])
    _drop_my_grant(EX)
    home = f"/applydesk/operator/exercises/{EX}"
    assert client.get(home).status_code == 404
    assert "Recruitment and Selection" not in client.get("/applydesk/operator/exercises").text
    diag = client.get("/applydesk/admin/exercises").text
    row = diag[diag.index(f'data-ex-row="{EX}"') :]
    row = row[: row.index("</tr>")]
    assert "data-adopt" in row and f"/admin/exercises/{EX}/manage" in row
    adopted = client.post(f"/applydesk/admin/exercises/{EX}/manage", follow_redirects=False)
    assert adopted.headers["location"].endswith(f"/operator/exercises/{EX}")
    assert client.get(home).status_code == 200
    assert "Recruitment and Selection" in client.get("/applydesk/operator/exercises").text
    assert _events()[-1] == "exercise.adopted"
    # Owned now: Manage is a plain link, and posting again adopts nothing.
    again = client.post(f"/applydesk/admin/exercises/{EX}/manage", follow_redirects=False)
    assert again.status_code == 303 and _events()[-1] == "exercise.adopted"
    assert _events().count("exercise.adopted") == 1
    diag = client.get("/applydesk/admin/exercises").text
    row = diag[diag.index(f'data-ex-row="{EX}"') :]
    assert "data-adopt" not in row[: row.index("</tr>")]


def test_adopting_beside_an_owner_leaves_two_owners(monkeypatch: pytest.MonkeyPatch) -> None:
    """An Admin adopting an exercise someone else owns becomes a second
    Owner; Diagnostics names both."""
    from applydesk.models import Exercise

    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", False)
    monkeypatch.setattr(identity_settings, "super_admin_emails", ["root@example.edu"])
    session = db.new_session()
    me = session.scalar(select(Person).where(Person.object_id == "local-dev"))
    assert me is not None
    me_id = me.id
    session.close()
    _drop_my_grant(EX)
    ann = _signed_in("ann@example.edu", "o-ann", "Ann Koh")
    _as(ann, "admit")
    session = db.new_session()
    ra = session.scalar(select(Exercise).where(Exercise.public_id == EX))
    ann_row = session.get(Person, ann)
    assert ra is not None and ann_row is not None
    operators.add_operator(session, ra, SUPER, ann_row)
    operators.transfer(session, ra, SUPER, ann_row)  # Ann owns RA
    session.commit()
    session.close()
    _as(me_id, "promote")
    client = TestClient(host_with(("applydesk",))[0])
    client.post(f"/applydesk/admin/exercises/{EX}/manage")
    session = db.new_session()
    ra = session.scalar(select(Exercise).where(Exercise.public_id == EX))
    assert ra is not None
    assert {p.id for p in operators.owners_of(session, ra)} == {ann, me_id}
    session.close()
    diag = client.get("/applydesk/admin/exercises").text
    row = diag[diag.index(f'data-ex-row="{EX}"') :]
    assert "Ann Koh, Local Operator" in row[: row.index("</tr>")]


def test_an_operator_cannot_adopt(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", False)
    _drop_my_grant(EX)
    client = TestClient(host_with(("applydesk",))[0])
    assert client.post(f"/applydesk/admin/exercises/{EX}/manage").status_code == 404
    from applydesk.models import Exercise

    session = db.new_session()
    me = session.scalar(select(Person).where(Person.object_id == "local-dev"))
    ra = session.scalar(select(Exercise).where(Exercise.public_id == EX))
    assert me is not None and ra is not None
    with pytest.raises(Refused) as refused:
        operators.adopt(session, ra, Actor(me))
    assert refused.value.key == "not_admin"
    session.close()


def test_the_last_admin_stays_one_with_a_super_admin_too() -> None:
    """Spec §8, as Review Robin's last_admin: never the last, whoever asks."""
    ben = _signed_in("ben@example.edu", "o-ben")
    _as(ben, "promote")
    session = db.new_session()
    row = session.get(Person, ben)
    assert row is not None
    with pytest.raises(Refused) as refused:
        operators.demote(session, SUPER, row)
    assert refused.value.key == "last_admin"
    session.close()


def test_a_super_admin_s_row_is_protected(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cold read: an Admin keeps the list, but no Revoke, Promote or
    Demote acts on a super-admin's row (spec §8)."""
    monkeypatch.setattr(identity_settings, "super_admin_emails", ["root@example.edu"])
    root = _signed_in("root@example.edu", "o-root", "Root")
    _as(root, "admit")
    session = db.new_session()
    row = session.get(Person, root)
    assert row is not None
    for change in (operators.revoke, operators.promote, operators.demote):
        with pytest.raises(Refused) as refused:
            change(session, SUPER, row)
        assert refused.value.key == "protected"
    session.close()


def test_a_bound_super_admin_holds_no_exercise_without_a_grant() -> None:
    """Cold read: the services, not only the gate, give a signed-in
    super-admin no implicit reach; only the seed's platform actor has it."""
    from applydesk.models import Exercise

    _drop_my_grant(EX)
    session = db.new_session()
    me = session.scalar(select(Person).where(Person.object_id == "local-dev"))
    ra = session.scalar(select(Exercise).where(Exercise.public_id == EX))
    assert me is not None and ra is not None
    for actor in (Actor(me, is_super_admin=True), Actor(None, is_super_admin=True)):
        assert not operators.can_operate(session, ra, actor)
        assert not operators.is_owner(session, ra, actor)
    assert operators.can_operate(session, ra, SUPER)  # the platform
    session.close()


def test_a_postgres_deadlock_is_a_lost_race() -> None:
    """Codex on #4132: Postgres aborting one of two transactions that each
    waited on the other is reported as a concurrent change, not a 500."""
    from sqlalchemy.exc import OperationalError

    def error(text: str) -> OperationalError:
        return OperationalError("UPDATE person", {}, Exception(text))

    assert db.lost_a_race(error("deadlock detected\nDETAIL: Process 1 waits for ShareLock"))
    assert db.lost_a_race(error("database is locked"))
    assert not db.lost_a_race(error("no such table: person"))
