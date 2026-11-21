"""The operator list, wired (segment AD2A, rung 6; ruling 75): the
super-admin searches people on record and the directory, admits and
revokes, each audited; no one else can post here."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from applydesk import db, operators, people
from applydesk.models import AuditEvent, Person
from applydesk.tests._host import host_with
from cordware.settings import identity_settings

JANE = "11111111-1111-4111-8111-111111111111"  # Cordware's fake directory


@pytest.fixture
def client() -> TestClient:
    """The conftest's super-admin."""
    return TestClient(host_with(("applydesk",))[0])


def _person(object_id: str) -> Person | None:
    session = db.new_session()
    try:
        return session.scalar(select(Person).where(Person.object_id == object_id))
    finally:
        session.close()


def _events() -> list[str]:
    session = db.new_session()
    try:
        return [e.event_type for e in session.scalars(select(AuditEvent).order_by(AuditEvent.id))]
    finally:
        session.close()


def _suggest(client: TestClient, q: str) -> dict[str, object]:
    answer = client.get("/applydesk/admin/operators/suggest", params={"q": q})
    assert answer.headers["cache-control"] == "no-store"
    return answer.json()


def test_the_search_shows_the_directory_and_admit_stores_them_bound(client: TestClient) -> None:
    offers = _suggest(client, "jane")
    assert offers["available"] is True
    assert offers["people"] == [
        {
            "label": "Jane Tan <jane.tan@example.edu>",
            "object_id": JANE,
            "address": "jane.tan@example.edu",
            "where": "Directory",
        }
    ]
    done = client.post(
        "/applydesk/admin/operators/admit",
        data={"object_id": JANE, "address": "jane.tan@example.edu"},
        follow_redirects=False,
    )
    assert done.status_code == 303 and done.headers["location"].endswith("said=admitted")
    jane = _person(JANE)
    assert jane is not None and jane.bound and jane.may_operate
    assert jane.admitted_by_id is not None  # the super-admin, bound at sign-in
    listed = client.get("/applydesk/admin/operators").text
    assert f'data-op-entry="{jane.id}"' in listed and "Added to the list." not in listed
    assert "person.admitted" in _events()
    assert _suggest(client, "jane")["people"] == []  # on record now, and already listed


def test_admit_on_record_then_revoke(client: TestClient) -> None:
    session = db.new_session()
    ed = people.pending(session, "ed@example.edu", actor=None)
    session.commit()
    ed_id = ed.id
    session.close()
    assert (
        client.post(
            "/applydesk/admin/operators/admit",
            data={"person_id": str(ed_id)},
            follow_redirects=False,
        )
        .headers["location"]
        .endswith("said=admitted")
    )
    again = client.post(
        "/applydesk/admin/operators/admit", data={"person_id": str(ed_id)}, follow_redirects=False
    )
    assert again.headers["location"].endswith("said=already_listed")
    gone = client.post(f"/applydesk/admin/operators/{ed_id}/revoke", follow_redirects=False)
    assert gone.headers["location"].endswith("said=revoked")
    session = db.new_session()
    kept = session.get(Person, ed_id)
    assert kept is not None and not operators.may_operate(kept)
    session.close()
    assert _events()[-2:] == ["person.admitted", "person.revoked"]
    # Still on record, so still a Workspace user (AD2W), no longer an operator.
    page = client.get("/applydesk/admin/operators?said=revoked&show=no_role").text
    assert f'data-op-entry="{kept.id}"' in page and "data-op-revoke data-name" not in page


def test_a_forged_directory_pick_is_refused(client: TestClient) -> None:
    """Nothing about the person comes from the form: the directory is asked
    again, and an object ID it does not give for that address is refused."""
    done = client.post(
        "/applydesk/admin/operators/admit",
        data={"object_id": "not-jane", "address": "jane.tan@example.edu"},
        follow_redirects=False,
    )
    assert done.headers["location"].endswith("said=gone")
    assert _person("not-jane") is None


def test_a_failing_directory_still_shows_people_on_record(client: TestClient) -> None:
    offers = _suggest(client, "outage@example.edu")
    assert offers["available"] is False and offers["reason"] == "server"
    done = client.post(
        "/applydesk/admin/operators/admit",
        data={"object_id": JANE, "address": "outage@example.edu"},
        follow_redirects=False,
    )
    assert done.headers["location"].endswith("said=directory")


def test_nobody_but_the_super_admin_can_post(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(identity_settings, "fake_auth_super_admin", False)
    other = TestClient(host_with(("applydesk",))[0])
    assert (
        other.post(
            "/applydesk/admin/operators/admit", data={"object_id": JANE, "address": "x"}
        ).status_code
        == 404
    )
    assert other.post("/applydesk/admin/operators/1/revoke").status_code == 404
    assert _person(JANE) is None


def test_a_post_from_another_site_is_refused(client: TestClient) -> None:
    done = client.post(
        "/applydesk/admin/operators/admit",
        data={"object_id": JANE, "address": "jane.tan@example.edu"},
        headers={"sec-fetch-site": "cross-site"},
    )
    assert done.status_code == 403


def test_the_directory_is_asked_off_the_event_loop(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Codex on #4113: Graph's calls block, so admission runs in a worker
    thread, never on the event loop the other requests share."""
    import asyncio

    from applydesk import routes_admin
    from cordware.graph import DirectoryUser, FakeDirectory

    seen: list[bool] = []

    class Watched(FakeDirectory):
        def find_users(self, address: str) -> list[DirectoryUser]:
            try:
                asyncio.get_running_loop()
                seen.append(True)  # on the loop
            except RuntimeError:
                seen.append(False)  # in a worker thread
            return super().find_users(address)

    monkeypatch.setattr(routes_admin, "directory_for", lambda request: Watched())
    client.post(
        "/applydesk/admin/operators/admit",
        data={"object_id": JANE, "address": "jane.tan@example.edu"},
    )
    assert seen == [False]


def test_back_keeps_where_admin_was_opened_from(client: TestClient) -> None:
    """Codex on #4115: searching, admitting and revoking keep the page Admin
    was opened from, so Back still goes there."""
    home = "/operator/exercises/wa9juxbc2t"
    back = f'href="/applydesk{home}" data-admin-back'
    page = client.get("/applydesk/admin/operators", params={"return_to": home}).text
    assert page.count(f'name="return_to" value="{home}"') >= 2  # Add and the table's search
    assert back in page
    admitted = client.post(
        "/applydesk/admin/operators/admit",
        data={"object_id": JANE, "address": "jane.tan@example.edu", "return_to": home},
    )
    assert back in admitted.text and "Added to the list." in admitted.text
    jane = _person(JANE)
    assert jane is not None
    revoked = client.post(f"/applydesk/admin/operators/{jane.id}/revoke", data={"return_to": home})
    assert back in revoked.text
    away = client.post(
        f"/applydesk/admin/operators/{jane.id}/revoke", data={"return_to": "//evil.example"}
    )
    assert 'href="/applydesk/operator/exercises" data-admin-back' in away.text


def test_the_super_admin_is_listed_as_self() -> None:
    """The author's ask (2026-11-21), as Review Robin's Accounts
    Management: the signed-in super-admin is on the list as (self), though
    they reach every page by their identity; once on the list themselves,
    their own row says so rather than a second one."""
    from applydesk import seed

    admin = TestClient(host_with(("applydesk",))[0])
    page = admin.get("/applydesk/admin/operators").text
    assert page.count("data-op-self") == 1 and "Super-admin" in page and "Nobody yet" not in page
    assert "data-op-self" not in admin.get("/applydesk/admin/operators?list_q=zzz").text
    session = db.new_session()
    seed.seed(session)  # puts the fake identity on the list
    me = _person("local-dev")
    session.close()
    assert me is not None
    page = admin.get("/applydesk/admin/operators").text
    assert page.count("data-op-self") == 1 and f'data-op-entry="{me.id}" data-op-self' in page
    row = page[page.index(f'data-op-entry="{me.id}"') :]
    row = row[: row.index("</tr>")]
    assert "(self)" in row and "Revoke" not in row  # no action on your own row (ruling)
    refused = admin.post(f"/applydesk/admin/operators/{me.id}/revoke", follow_redirects=False)
    assert refused.headers["location"].endswith("said=self")
    after = _person("local-dev")
    assert after is not None and after.may_operate


def test_workspace_users_scaffold() -> None:
    """AD2W rung 2: everyone on record in Review Robin's columns, the two
    panes over the table, the chips, the exercise role and the bulk bar
    inert until built; a pending person is listed, not yet signed in."""
    session = db.new_session()
    pending = people.pending(session, "pat@example.edu", None)
    session.commit()
    pid = pending.id
    session.close()
    admin = TestClient(host_with(("applydesk",))[0])
    page = admin.get("/applydesk/admin/operators?show=unused").text
    table = page[page.index("data-op-list") :]
    for heading in ("Email", "Name", "Unit", "First sign-in", "Operator", "Admin"):
        assert f"<th>{heading}</th>" in table
    assert '<h2 id="op-list-h">Workspace users</h2>' in page
    assert page.count("data-account-chip=") == 4 and "data-account-role" in page
    assert "Acting on ticked rows is not built yet" in page
    assert "pat@example.edu" not in admin.get("/applydesk/admin/operators").text  # Unused: off
    row = table[table.index(f'data-op-entry="{pid}"') :]
    row = row[: row.index("</tr>")]
    assert "pat@example.edu" in row and "Not yet signed in" in row and "data-op-revoke" not in row


def test_chips_and_exercise_role_filter_workspace_users() -> None:
    """AD2W rung 3, as Review Robin's: each person under one chip (the
    super-admin's own row Admins, then operators, then anyone with a
    history No role, else Unused); the counts take the role and search
    but not the chips; no `show` is the default chips, a blank one none."""
    from applydesk import seed
    from applydesk.models import Exercise
    from applydesk.operators import Actor

    session = db.new_session()
    seed.seed(session)  # the fake super-admin: listed, Owner of every sample
    sup = Actor(None, is_super_admin=True)

    def bound(oid: str, mail: str, name: str) -> Person:
        from cordware.identity import Identity

        p = people.resolve(
            session, Identity(principal_id=oid, email=mail, name=name, tenant_id="local-tenant")
        )
        assert p is not None
        return p

    ana = bound("o-ana", "ana@example.edu", "Ana Lim")
    ben = bound("o-ben", "ben@example.edu", "Ben Ong")
    cat = bound("o-cat", "cat@example.edu", "Cat Tan")
    for p in (ana, ben, cat):
        operators.admit(session, sup, p)
    operators.revoke(session, sup, cat)
    exercise = session.scalar(select(Exercise).where(Exercise.public_id == "wa9juxbc2t"))
    assert exercise is not None
    operators.add_operator(session, exercise, sup, ben)
    people.pending(session, "pat@example.edu", None)
    session.commit()
    ids = {"ana": ana.id, "ben": ben.id, "cat": cat.id}
    session.close()

    admin = TestClient(host_with(("applydesk",))[0])

    def rows(query: str = "") -> set[str]:
        page = admin.get("/applydesk/admin/operators" + query).text
        table = page[page.index("data-op-list") :]
        return {n for n, i in ids.items() if f'data-op-entry="{i}"' in table} | (
            {"pat"} if "pat@example.edu" in table else set()
        )

    page = admin.get("/applydesk/admin/operators").text
    for chip in ("Operators (2)", "Admins (1)", "No role (1)", "Unused (1)"):
        assert chip in page, chip
    assert rows() == {"ana", "ben"}  # the defaults: Operators and Admins
    assert rows("?show=no_role&show=unused") == {"cat", "pat"}
    assert rows("?show=") == set()  # every chip off
    assert "No one matches the chips" in admin.get("/applydesk/admin/operators?show=").text
    assert rows("?show=bogus&show=operators") == {"ana", "ben"}  # unknown chips ignored
    assert rows("?role=operator") == {"ben"}  # a current grant on some exercise
    assert rows("?role=none&show=operators&show=no_role") == {"ana", "cat"}
    assert rows("?role=owner") == set()  # only the super-admin owns, under Admins
    assert "data-op-self" in admin.get("/applydesk/admin/operators?role=owner").text
    owner_page = admin.get("/applydesk/admin/operators?role=owner").text
    assert "Operators (0)" in owner_page and "Admins (1)" in owner_page
    assert rows("?list_q=ben") == {"ben"}
    cleared = admin.get("/applydesk/admin/operators?list_q=ben").text
    assert "data-account-clear" in cleared and "data-account-clear" not in page


def test_add_offers_records_first_and_takes_only_a_pick(client: TestClient) -> None:
    """AD2W rung 4, as Review Robin's Invite card: one box offering people
    on record not yet listed, then the directory; Cancel and Add under it,
    Add posting the pick. Typed text that is no pick is refused politely."""
    session = db.new_session()
    pat = people.pending(session, "jane.pat@example.edu", None)
    session.commit()
    pid = pat.id
    session.close()
    offers = _suggest(client, "jane")["people"]
    assert isinstance(offers, list) and offers[0] == {
        "label": "jane.pat@example.edu",
        "person_id": pid,
        "where": "On record",
    }
    assert offers[1]["where"] == "Directory"
    page = client.get("/applydesk/admin/operators").text
    card = page[page.index("data-op-add") : page.index('id="accounts-overview"')]
    assert "data-op-add-cancel" in card and "data-op-add-submit" in card and ">Search<" not in card
    typed = client.post(
        "/applydesk/admin/operators/admit", data={"person_id": ""}, follow_redirects=False
    )
    assert typed.headers["location"].endswith("said=pick")
    assert _suggest(client, "j")["people"] == []  # under the shortest query


def test_two_people_with_one_label_stay_two_picks() -> None:
    """Codex on #4122: the box finds a pick by its label, so two accounts
    sharing a name and address must not share a label."""
    from applydesk import allowlist
    from applydesk.directory import SearchResult
    from cordware.graph import DirectoryUser

    twins = tuple(
        DirectoryUser(
            id=oid, display_name="Sam Lee", mail="sam@example.edu", user_principal_name="sam@x"
        )
        for oid in ("o-1", "o-2")
    )
    offers = allowlist.suggestions(SearchResult((), twins), set())["people"]
    assert isinstance(offers, list)
    labels = [o["label"] for o in offers]
    assert labels == ["Sam Lee <sam@example.edu>", "Sam Lee <sam@example.edu> (directory 2)"]
    assert [o["object_id"] for o in offers] == ["o-1", "o-2"]


def test_listed_people_never_crowd_the_suggestions_out(client: TestClient) -> None:
    """Codex on #4122: with a full page of listed matches, the one person
    who can still be added is offered, not lost to the search's limit."""
    from applydesk import directory as directory_mod
    from applydesk.operators import Actor

    session = db.new_session()
    sup = Actor(None, is_super_admin=True)
    for n in range(directory_mod.LIMIT):
        operators.admit(session, sup, people.pending(session, f"lim{n:02}@example.edu", None))
    last = people.pending(session, "lim.zz@example.edu", None)
    session.commit()
    last_id = last.id
    session.close()
    offers = _suggest(client, "lim")["people"]
    assert isinstance(offers, list)
    assert [o["person_id"] for o in offers if "person_id" in o] == [last_id]
