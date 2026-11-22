"""The Operator Lobby wired (segment AD2B rung 6): sorting, the tag chips
and the filter by query string; the panel's Save, tag actions, Duplicate
settings only, Archive and Delete; the Archive's Restore."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from applydesk import db, exercises, lobby, sample_data
from applydesk.models import AuditEvent, Exercise, ExerciseOperator
from applydesk.tests._host import host_with

LOBBY = "/applydesk/operator/exercises"
PANEL = f"{LOBBY}/panel"
RA, BLANK, SIS = "wa9juxbc2t", "n5wg8tjr3e", "c4xh2ndv6s"


def _client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0], follow_redirects=False)


def _post(client: TestClient, **fields: Any) -> str:
    """A panel post; the status line it comes back with."""
    reply = client.post(PANEL, data=fields)
    assert reply.status_code == 303, reply.text
    page = client.get(reply.headers["location"]).text
    start = page.find("data-nx-said>")
    return page[start + len("data-nx-said>") : page.find("</p>", start)] if start >= 0 else ""


def _row(public_id: str) -> Exercise:
    session = db.new_session()
    found = session.scalars(select(Exercise).where(Exercise.public_id == public_id)).one()
    session.close()
    return found


def _rows_in(page: str) -> list[str]:
    return [e.public_id for e in sample_data.EXERCISES if f'data-id="{e.public_id}"' in page]


def _order(page: str) -> list[str]:
    ids = _rows_in(page)
    return sorted(ids, key=lambda i: page.index(f'data-id="{i}"'))


# --- Sorting, tags and the filter -------------------------------------------


def test_sorting_is_by_query_string_and_flips() -> None:
    client = _client()
    by_name = _order(client.get(f"{LOBBY}?sort=name&dir=asc").text)
    names = [e.name.casefold() for i in by_name if (e := sample_data.exercise(i)) is not None]
    assert names == sorted(names)
    assert _order(client.get(f"{LOBBY}?sort=name&dir=desc").text) == by_name[::-1]
    page = client.get(f"{LOBBY}?sort=name&dir=asc").text
    assert (
        'aria-sort="ascending"><a href="/applydesk/operator/exercises?sort=name&amp;dir=desc"'
        in page
    )


def test_an_unknown_sort_is_ignored_not_echoed() -> None:
    page = _client().get(f"{LOBBY}?sort=%3Cscript%3E&dir=up").text
    assert "<script>" not in page.split("<body", 1)[1].split("<script", 1)[0]
    assert (
        'aria-sort="descending"><a href="/applydesk/operator/exercises?sort=created&amp;dir=asc"'
        in page
    )


def test_tag_chips_narrow_with_and_and_widen_with_or() -> None:
    """No sample carries both Residential and Grants: none under AND; RA-2027
    (Residential) and the two Grants exercises under OR."""
    client = _client()
    pair = [("tag", "Residential"), ("tag", "Grants")]
    assert _rows_in(client.get(LOBBY, params=pair).text) == []
    either = _rows_in(client.get(LOBBY, params=[*pair, ("any", "1")]).text)
    assert sorted(either) == sorted([RA, "r6tm4kq9wz", BLANK])
    page = client.get(LOBBY, params=[("tag", "Residential")]).text
    assert 'aria-current="true" data-lb-chip>Residential<' in page


def test_the_filter_matches_name_code_or_tag_ignoring_case() -> None:
    client = _client()
    assert _rows_in(client.get(LOBBY, params={"q": "ra-2027"}).text) == [RA]
    assert RA in _rows_in(client.get(LOBBY, params={"q": "RESIDENTIAL"}).text)
    page = client.get(LOBBY, params={"q": "no such thing"}).text
    assert "data-lb-none-shown" in page and "No exercise matches" in page


def test_the_query_rebuilds_itself_and_drops_what_it_does_not_know() -> None:
    q = lobby.Query.parse({"sort": "code", "dir": "asc", "q": " x ", "evil": "1"}, ["a", "A", ""])
    assert q.href("/l") == "/l?sort=code&dir=asc&tag=a&q=x"


# --- The panel -----------------------------------------------------------------


def test_save_renames_recodes_and_retags_one_exercise() -> None:
    """SIS-2027 is a draft, so its code may change."""
    said = _post(
        _client(),
        action="save",
        id=SIS,
        revision=str(_row(SIS).revision),
        name="SIS 2027",
        code="SIS-27",
        tags="Interns, summer , INTERNS",
    )
    assert said == "Saved."
    row = _row(SIS)
    assert (row.name, row.code, row.code_key) == ("SIS 2027", "SIS-27", "sis-27")
    session = db.new_session()
    assert exercises.tags_of(session, row) == ("Interns", "summer")
    session.close()


def test_a_stale_or_clashing_save_saves_nothing() -> None:
    client = _client()
    assert _post(client, action="save", id=RA, revision="0", name="X", code="", tags="") == (
        "Not saved: someone else changed it just now. Look again and retry."
    )
    blank = _row(BLANK)
    said = _post(
        client,
        action="save",
        id=BLANK,
        revision=str(blank.revision),
        name="G",
        code="ra-2027",
        tags="",
    )
    assert said == "Not saved: another live exercise has that code."
    assert _row(BLANK).name == blank.name


def test_tags_go_to_all_and_come_off_all() -> None:
    client = _client()
    assert _post(client, action="add_tags", id=[RA, BLANK], tags="Shared, shared") == "Tags added."
    session = db.new_session()
    assert "Shared" in exercises.tags_of(session, _row(BLANK))
    session.close()
    assert _post(client, action="remove_tags", id=[RA, BLANK], tags="SHARED") == "Tags removed."
    session = db.new_session()
    assert "Shared" not in exercises.tags_of(session, _row(RA))
    session.close()
    assert _post(client, action="add_tags", id=[RA], tags=" , ") == "Type the tags first."
    too_many = ", ".join(f"t{i}" for i in range(21))
    assert _post(client, action="add_tags", id=[RA], tags=too_many).startswith(
        "Not saved: an exercise carries"
    )


def test_archive_moves_it_to_the_archive_and_restore_brings_it_back() -> None:
    client = _client()
    assert _post(client, action="archive", id=RA) == "Archived: see Go to Archive."
    assert RA not in _rows_in(client.get(LOBBY).text)
    assert "Recruitment and Selection" in client.get(f"{LOBBY}/archived").text
    # Its code is free: another exercise takes it, so Restore is refused.
    blank = _row(BLANK)
    _post(
        client,
        action="save",
        id=BLANK,
        revision=str(blank.revision),
        name="G",
        code="RA-2027",
        tags="",
    )
    reply = client.post(f"{LOBBY}/archived/restore", data={"id": RA})
    assert "restore_taken" in reply.headers["location"]
    blank = _row(BLANK)
    _post(client, action="save", id=BLANK, revision=str(blank.revision), name="G", code="", tags="")
    reply = client.post(f"{LOBBY}/archived/restore", data={"id": RA})
    assert "restored" in reply.headers["location"] and _row(RA).archived_at is None
    assert RA in _rows_in(client.get(LOBBY).text)


def test_delete_asks_first_and_then_the_exercise_leaves_every_page() -> None:
    client = _client()
    assert _post(client, action="delete", id=BLANK) == "Not deleted: tick Yes, delete first."
    assert _post(client, action="delete", id=BLANK, confirm="yes") == "Deleted."
    assert BLANK not in _rows_in(client.get(LOBBY).text)
    assert client.get(f"{LOBBY}/{BLANK}").status_code == 404
    # Every page: the Admin's Diagnostics and the applicant's /me too, and
    # Manage cannot adopt it.
    assert "Graduate Travel Grant" not in client.get("/applydesk/admin/exercises").text
    assert "Graduate Travel Grant" not in client.get("/applydesk/me").text
    manage = client.post(f"/applydesk/admin/exercises/{BLANK}/manage")
    assert "not_loaded" in manage.headers["location"]
    session = db.new_session()
    kinds = list(session.scalars(select(AuditEvent.event_type)))
    session.close()
    assert "exercise.deleted" in kinds  # the audit trail stays


def test_archive_and_delete_are_owner_only() -> None:
    """An operator who is not an Owner is refused, and nothing changes."""
    session = db.new_session()
    grant = session.scalars(
        select(ExerciseOperator).join(Exercise).where(Exercise.public_id == RA)
    ).one()
    grant.is_owner = False
    session.commit()
    session.close()
    client = _client()
    message = "Only an exercise&#39;s Owner may archive, restore or delete it."
    assert _post(client, action="archive", id=RA) == message
    assert _post(client, action="delete", id=RA, confirm="yes") == message
    assert _row(RA).archived_at is None and _row(RA).deleted_at is None
    # Restore too: archived by hand, a non-Owner cannot bring it back.
    session = db.new_session()
    row = session.scalars(select(Exercise).where(Exercise.public_id == RA)).one()
    row.archived_at = row.created_at
    session.commit()
    session.close()
    reply = client.post(f"{LOBBY}/archived/restore", data={"id": RA})
    assert "not_owner" in reply.headers["location"] and _row(RA).archived_at is not None


def test_duplicate_settings_only_makes_a_copy_named_and_owned_by_the_viewer() -> None:
    client = _client()
    reply = client.post(PANEL, data={"action": "duplicate", "id": RA})
    assert reply.status_code == 303
    made = reply.headers["location"].rsplit("/", 1)[1]
    copy = _row(made)
    assert (copy.name, copy.code) == (
        "Copy of Recruitment and Selection of Residential Assistants",
        None,
    )
    assert copy.help_contact == _row(RA).help_contact
    session = db.new_session()
    assert exercises.tags_of(session, copy) == exercises.tags_of(session, _row(RA))
    session.close()
    home = client.get(reply.headers["location"], cookies=reply.cookies)
    assert home.status_code == 200 and "Copy of Recruitment" in home.text
    session = db.new_session()
    grant = session.scalars(
        select(ExerciseOperator).where(ExerciseOperator.exercise_id == copy.id)
    ).one()
    session.close()
    assert grant.is_owner and copy.created_by_id == grant.person_id  # the duplicator's


@pytest.mark.parametrize("action", ["", "explode"])
def test_an_unknown_action_is_refused(action: str) -> None:
    assert _client().post(PANEL, data={"action": action, "id": RA}).status_code == 400


def test_a_published_exercise_s_code_is_fixed_in_the_lobby_too() -> None:
    """Codex on #4140: RA-2027 is published; its name and tags save, its
    code does not."""
    client = _client()
    revision = str(_row(RA).revision)
    said = _post(client, action="save", id=RA, revision=revision, name="RA", code="RA-28", tags="")
    assert said.startswith("Not saved: a published exercise") and _row(RA).code == "RA-2027"
    said = _post(
        client, action="save", id=RA, revision=revision, name="RA", code="RA-2027", tags=""
    )
    assert said == "Saved." and _row(RA).name == "RA"


def test_my_applications_leave_with_a_deleted_exercise() -> None:
    """Codex on #4140: an application in a deleted exercise leaves /me."""
    mine = sample_data.my_applications()
    assert mine
    gone = mine[0].exercise_id
    session = db.new_session()
    row = session.scalars(select(Exercise).where(Exercise.public_id == gone)).one()
    row.deleted_at = row.created_at
    session.commit()
    session.close()
    page = _client().get("/applydesk/me").text
    assert all(a.public_id not in page for a in mine if a.exercise_id == gone)
