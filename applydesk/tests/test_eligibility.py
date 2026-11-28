"""Who may apply (segment AD4A; ruling 84): `eligibility.may_apply` follows
the Form's *Who may apply* as stored: anyone signed in, the invite list, or
the people Create dossiers holds a dossier for."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from applydesk import candidates, db, eligibility, exercises, invitees, operators, people
from applydesk.models import Exercise, Person
from applydesk.models import Stage as StageRow

pytestmark = pytest.mark.usefixtures("applydesk_db")


def _exercise(eligibility_: str | None = None, *, create_dossiers: bool = False) -> str:
    session = db.new_session()
    owner = session.scalars(select(Person).where(Person.may_operate)).first()
    assert owner is not None
    made = exercises.make(session, operators.Actor(owner), "Who may apply")
    row = session.scalars(select(Exercise).where(Exercise.public_id == made.public_id)).one()
    row.eligibility = eligibility_
    session.add(
        StageRow(
            exercise_id=row.id,
            key="s1",
            position=1,
            holds_form=not create_dossiers,
            holds_candidates=create_dossiers,
        )
    )
    if create_dossiers:
        session.add(StageRow(exercise_id=row.id, key="s2", position=2, holds_form=True))
    session.commit()
    public_id = row.public_id
    session.close()
    return public_id


def _why(public_id: str, address: str | None) -> str | None:
    session = db.new_session()
    try:
        row = session.scalars(select(Exercise).where(Exercise.public_id == public_id)).one()
        person = people.pending(session, address, None) if address else None
        return eligibility.may_apply(session, row, person)
    finally:
        session.rollback()
        session.close()


def _add(public_id: str, address: str, svc: object) -> None:
    """Put ``address`` on the invite list or Create dossiers' entries."""
    session = db.new_session()
    # The person on record (bound, as the fake identity is), else pending.
    person = session.scalars(
        select(Person).where(Person.email_key == address).order_by(Person.id)
    ).first() or people.pending(session, address, None)
    if svc is invitees:
        invitees.add(session, public_id, person, "search", None)
    else:
        candidates.add(session, public_id, person, "search", None)
    session.commit()
    session.close()


@pytest.mark.parametrize("stored", ["open", None])
def test_anyone_signed_in_may_apply(stored: str | None) -> None:
    ex = _exercise(stored)
    assert _why(ex, "ann@example.edu") == "open"


def test_no_one_signed_in_may_not() -> None:
    assert _why(_exercise("open"), None) is None


def test_invitees_only_the_invited_and_not_once_removed() -> None:
    ex = _exercise("invitation")
    _add(ex, "ann@example.edu", invitees)
    assert _why(ex, "ann@example.edu") == "invited"
    assert _why(ex, "bob@example.edu") is None
    session = db.new_session()
    entry = invitees.listing(session, ex)[0].id
    invitees.remove(session, ex, entry, None)
    session.commit()
    session.close()
    assert _why(ex, "ann@example.edu") is None


def test_create_dossiers_admits_the_people_it_holds_dossiers_for() -> None:
    """With Create dossiers on the timeline the Form writes to its dossiers
    (ruling 83), whatever the stored eligibility says."""
    ex = _exercise("invitation", create_dossiers=True)
    _add(ex, "ann@example.edu", candidates)
    assert _why(ex, "ann@example.edu") == "dossier"
    assert _why(ex, "bob@example.edu") is None
    session = db.new_session()
    candidates.remove(session, ex, candidates.listing(session, ex)[0].id, None)
    session.commit()
    session.close()
    assert _why(ex, "ann@example.edu") is None


def test_an_archived_exercise_admits_no_one() -> None:
    ex = _exercise("open")
    session = db.new_session()
    row = session.scalars(select(Exercise).where(Exercise.public_id == ex)).one()
    row.archived_at = datetime.now(UTC)
    session.commit()
    session.close()
    assert _why(ex, "ann@example.edu") is None


def test_open_to_me_lists_only_what_admits_the_viewer() -> None:
    """Segment AD4A: the User Lobby's *Open to me* follows *Who may apply*:
    an invitation-only exercise shows, chipped, once the viewer (the fake
    identity, admin@example.edu) is invited."""
    from fastapi.testclient import TestClient

    from applydesk.tests._host import host_with

    ex = _exercise("invitation")
    session = db.new_session()
    row = session.scalars(select(Exercise).where(Exercise.public_id == ex)).one()
    row.name = "Invited Fellowship"
    row.process_revision = 1  # saved by Process, so its stages are read
    for stage in session.scalars(select(StageRow).where(StageRow.exercise_id == row.id)):
        stage.status = "published"
    session.commit()
    session.close()
    client = TestClient(host_with(("applydesk",))[0])
    assert "Invited Fellowship" not in client.get("/applydesk/me").text
    _add(ex, "admin@example.edu", invitees)
    lobby = client.get("/applydesk/me").text
    shown = lobby[lobby.index("Invited Fellowship") :]
    assert "You are invited" in shown[: shown.index("</p>")]


def test_the_lobby_reads_the_stored_form_state() -> None:
    """Codex on #4273: an exercise made with New exercise says
    Applications open or closed as its form is stored, not by the
    placeholder's flag."""
    from fastapi.testclient import TestClient

    from applydesk.tests._host import host_with

    ex = _exercise("open")
    session = db.new_session()
    row = session.scalars(select(Exercise).where(Exercise.public_id == ex)).one()
    row.name = "Stored Form"
    row.process_revision = 1
    for stage in session.scalars(select(StageRow).where(StageRow.exercise_id == row.id)):
        stage.status = "published"
        stage.form_state = "closed"
    session.commit()
    session.close()
    client = TestClient(host_with(("applydesk",))[0])
    lobby = client.get("/applydesk/me").text
    shown = lobby[lobby.index("Stored Form") :]
    assert "Applications closed" in shown[: shown.index("</p>")]
    page = client.get(f"/applydesk/me/exercises/{ex}").text
    assert "Start an application" not in page


def test_an_archived_exercise_leaves_me() -> None:
    """Codex on #4273: an exercise made with New exercise reads Draft
    whatever is stored, so its archiving is read from the row: archived,
    it leaves the lobby and its page is a 404."""
    from fastapi.testclient import TestClient

    from applydesk.tests._host import host_with

    ex = _exercise("open")
    session = db.new_session()
    row = session.scalars(select(Exercise).where(Exercise.public_id == ex)).one()
    row.name = "Soon Archived"
    row.process_revision = 1
    for stage in session.scalars(select(StageRow).where(StageRow.exercise_id == row.id)):
        stage.status = "published"
    session.commit()
    session.close()
    client = TestClient(host_with(("applydesk",))[0])
    assert "Soon Archived" in client.get("/applydesk/me").text
    assert client.get(f"/applydesk/me/exercises/{ex}").status_code == 200
    session = db.new_session()
    row = session.scalars(select(Exercise).where(Exercise.public_id == ex)).one()
    row.archived_at = datetime.now(UTC)
    session.commit()
    session.close()
    assert "Soon Archived" not in client.get("/applydesk/me").text
    assert client.get(f"/applydesk/me/exercises/{ex}").status_code == 404
