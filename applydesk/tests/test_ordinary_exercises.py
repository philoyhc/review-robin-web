"""Ordinary exercises (segment AD2G Item 1, rung 2): every live row that
is not a sample is an exercise, read from the database, reached through
its grants rather than one browser's store."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from applydesk import db, exercises, operators, people, sample_data, seed
from applydesk.models import Exercise, Person
from applydesk.tests._host import host_with
from cordware.settings import identity_settings

LOBBY = "/applydesk/operator/exercises"


def _row(public_id: str, name: str | None, *, ago: int = 0) -> None:
    """A row made as *New exercise* makes one, owned by the signed-in
    fake identity, `ago` minutes in the past."""
    session = db.new_session()
    try:
        person = people.resolve(
            session,
            seed._fake_identity(identity_settings),  # pyright: ignore[reportPrivateUsage]  -- the signed-in fake, as the seed binds it
        )
        actor = operators.Actor(person, is_super_admin=True)
        made = operators.create_exercise(session, actor, public_id, name)
        made.created_at = datetime.now(UTC) - timedelta(minutes=ago)
        session.commit()
    finally:
        session.close()


def _client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0], follow_redirects=False)


def test_a_sample_is_a_sample_and_nothing_else_is() -> None:
    assert all(sample_data.is_sample(e.public_id) for e in sample_data.EXERCISES)
    assert not sample_data.is_sample("zzzzzzzzzz")


def test_a_row_reads_as_a_blank_draft_named_by_it() -> None:
    _row("k7m2p9q4rt", "Summer Bursary 2027")
    found = sample_data.exercise("k7m2p9q4rt")
    assert found is not None
    assert (found.name, found.state, found.code, found.opens) == (
        "Summer Bursary 2027",
        "Draft",
        "",
        "Not set",
    )
    assert found.created.endswith("+00:00")


def test_a_row_with_no_name_is_untitled() -> None:
    _row("k7m2p9q4ru", None)
    found = sample_data.exercise("k7m2p9q4ru")
    assert found is not None and found.name == exercises.UNTITLED


def test_ordinary_exercises_come_first_newest_first_deleted_left_out() -> None:
    _row("k7m2p9q4ra", "Older", ago=10)
    _row("k7m2p9q4rb", "Newer", ago=1)
    _row("k7m2p9q4rc", "Gone")
    session = db.new_session()
    try:
        gone = exercises.row(session, "k7m2p9q4rc")
        assert gone is not None
        gone.deleted_at = datetime.now(UTC)
        session.commit()
    finally:
        session.close()
    ids = [e.public_id for e in sample_data.exercises()]
    assert ids[:2] == ["k7m2p9q4rb", "k7m2p9q4ra"]
    assert "k7m2p9q4rc" not in ids
    assert ids[2:] == [e.public_id for e in sample_data.EXERCISES]
    assert sample_data.exercise("k7m2p9q4rc") is None


def test_a_sample_never_reads_from_a_row_as_ordinary() -> None:
    sample = sample_data.EXERCISES[0]
    assert exercises.ordinary(sample.public_id) is None
    assert sample_data.exercise(sample.public_id) is sample


def test_the_lobby_lists_a_row_made_outside_any_browser() -> None:
    _row("k7m2p9q4rd", "Made elsewhere")
    client = _client()
    lobby = client.get(LOBBY).text
    assert "Made elsewhere" in lobby
    assert client.get(f"{LOBBY}/k7m2p9q4rd").status_code == 200


def test_an_ordinary_exercise_starts_with_a_blank_form_and_emails() -> None:
    from applydesk import workflow

    _row("k7m2p9q4re", "Blank")
    assert sample_data.form_is_empty("k7m2p9q4re")
    assert workflow._blank_emails("k7m2p9q4re")  # pyright: ignore[reportPrivateUsage]  -- the rule itself
    assert not workflow._blank_emails(sample_data.EXERCISES[0].public_id)  # pyright: ignore[reportPrivateUsage]  -- as above


def test_diagnostics_lists_ordinary_exercises() -> None:
    _row("k7m2p9q4rf", "On Diagnostics")
    client = _client()
    assert "On Diagnostics" in client.get("/applydesk/admin/exercises").text


def test_new_exercise_records_its_name_on_the_row() -> None:
    client = _client()
    made = client.post(f"{LOBBY}/new", data={"name": "Named at birth"})
    assert made.status_code == 303, made.text
    public_id = made.headers["location"].rsplit("/", 1)[1]
    session = db.new_session()
    try:
        found = session.query(Exercise).filter_by(public_id=public_id).one()
        assert found.name == "Named at birth"
    finally:
        session.close()


def test_the_seed_leaves_ordinary_exercises_alone() -> None:
    """Cold read: the seed walks the samples, not every exercise, so a
    second run neither records sample settings on an ordinary row nor
    counts it."""
    _row("k7m2p9q4rg", "Mine")
    session = db.new_session()
    try:
        result = seed.seed(session)
        assert result.exercises_added == 0
        found = exercises.row(session, "k7m2p9q4rg")
        assert found is not None and (found.name, found.revision) == ("Mine", 0)
    finally:
        session.close()


def test_another_operator_s_drafts_stay_theirs_until_they_add_you() -> None:
    """Cold read: the Lobby and Home show an ordinary exercise only to
    those who operate it; its name never reaches another operator's page,
    not even in Details' code list; a co-operator added on it sees it."""
    from cordware.identity import Identity

    _row("k7m2p9q4rh", "Mine")
    session = db.new_session()
    try:
        platform = operators.Actor(None, is_super_admin=True, platform=True)
        ben = people.resolve(
            session, Identity(principal_id="o-ben", email="ben@x.edu", name="Ben", tenant_id="t")
        )
        assert ben is not None
        operators.admit(session, platform, ben)
        theirs = operators.create_exercise(
            session, operators.Actor(ben), "k7m2p9q4rj", "Bens Draft"
        )
        theirs.code, theirs.code_key, theirs.revision = "BEN-1", "ben-1", 1
        session.commit()
        ben_id = ben.id
    finally:
        session.close()
    client = _client()
    assert "Bens Draft" not in client.get(LOBBY).text
    assert client.get(f"{LOBBY}/k7m2p9q4rj").status_code == 404
    home = client.get(f"{LOBBY}/k7m2p9q4rh").text
    assert "Bens Draft" not in home and "BEN-1" not in home
    # Ben adds the viewer as an operator: now it is theirs to see too.
    session = db.new_session()
    try:
        me = people.resolve(session, seed._fake_identity(identity_settings))  # pyright: ignore[reportPrivateUsage]  -- the signed-in fake
        found = exercises.row(session, "k7m2p9q4rj")
        ben = session.get(Person, ben_id)
        assert me is not None and found is not None and ben is not None
        operators.add_operator(session, found, operators.Actor(ben), me)
        session.commit()
    finally:
        session.close()
    assert "Bens Draft" in _client().get(LOBBY).text
    assert _client().get(f"{LOBBY}/k7m2p9q4rj").status_code == 200


def test_a_code_clash_with_an_exercise_you_do_not_operate_names_neither() -> None:
    _row("k7m2p9q4rk", "Mine")
    session = db.new_session()
    try:
        other = exercises.row(session, "k7m2p9q4rk")
        assert other is not None
        sample = exercises.row(session, sample_data.EXERCISES[0].public_id)
        assert sample is not None and sample.code and sample.name
        code, name = sample.code, sample.name
        with pytest.raises(exercises.Refused) as refused:
            exercises.save_panel(session, "k7m2p9q4rk", "Mine", code, [], 0, None)
        assert "another live exercise" in str(refused.value)
        assert name not in str(refused.value)
    finally:
        session.close()


def test_a_fresh_ordinary_exercise_is_not_recorded_as_a_sample() -> None:
    """Cold read: its first panel save neither renames it nor audits a
    sample's settings; the row's own values stand."""
    from sqlalchemy import select

    from applydesk.models import AuditEvent

    _row("k7m2p9q4rm", "Fresh")
    session = db.new_session()
    try:
        exercises.retag(session, ["k7m2p9q4rm"], ["x"], add=True, actor=None)
        session.commit()
        found = exercises.row(session, "k7m2p9q4rm")
        assert found is not None and (found.name, found.revision) == ("Fresh", 2)
        assert not session.scalar(
            select(AuditEvent).where(
                AuditEvent.exercise_id == found.id,
                AuditEvent.event_type == "exercise.settings_recorded",
            )
        )
    finally:
        session.close()
