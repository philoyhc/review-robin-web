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


def test_the_search_shows_the_directory_and_admit_stores_them_bound(client: TestClient) -> None:
    page = client.get("/applydesk/admin/operators", params={"q": "jane"}).text
    assert 'data-op-hit="directory"' in page and "Jane Tan" in page
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
    again = client.get("/applydesk/admin/operators", params={"q": "jane"}).text
    assert 'data-op-hit="record"' in again and 'chip-ok">Operator<' in again  # now on record


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
    page = client.get("/applydesk/admin/operators?said=revoked").text
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
    page = client.get("/applydesk/admin/operators", params={"q": "outage@example.edu"}).text
    assert "data-op-directory-failed" in page and "(server)" in page
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
    assert page.count(f'name="return_to" value="{home}"') >= 2  # both searches
    found = client.get("/applydesk/admin/operators", params={"q": "jane", "return_to": home})
    assert back in found.text and f'name="return_to" value="{home}"' in found.text  # Admit too
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
    page = admin.get("/applydesk/admin/operators").text
    table = page[page.index("data-op-list") :]
    for heading in ("Email", "Name", "Unit", "First sign-in", "Operator", "Admin"):
        assert f"<th>{heading}</th>" in table
    assert '<h2 id="op-list-h">Workspace users</h2>' in page
    assert page.count("data-account-chip=") == 4 and "data-account-role" in page
    assert "Acting on ticked rows is not built yet" in page
    row = table[table.index(f'data-op-entry="{pid}"') :]
    row = row[: row.index("</tr>")]
    assert "pat@example.edu" in row and "Not yet signed in" in row and "data-op-revoke" not in row
