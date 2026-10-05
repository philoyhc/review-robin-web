"""A session code another session holds is a 422 form error, not a 500.

``sessions.code`` is unique across the workspace (a database
constraint). Create, Session Home's Save and the lobby's row-expander
Save each refuse a taken code before writing anything, rather than
letting the unique constraint raise ``IntegrityError``."""
from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from app.services import session_tags


def _create(client: TestClient, db: Session, name: str, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions",
        data={"name": name, "code": code},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == code)
    ).scalar_one()


def test_create_with_a_taken_code_is_a_422_and_writes_nothing(
    client: TestClient, db: Session
) -> None:
    _create(client, db, "First", "taken-code")

    response = client.post(
        "/operator/sessions",
        data={"name": "Second", "code": "taken-code"},
        follow_redirects=False,
    )

    assert response.status_code == 422, response.text
    assert "already used by another session" in response.text
    names = db.execute(select(ReviewSession.name)).scalars().all()
    assert names == ["First"]


def test_session_home_save_with_a_taken_code_is_a_422_and_writes_nothing(
    client: TestClient, db: Session
) -> None:
    _create(client, db, "Holder", "held-code")
    other = _create(client, db, "Other", "other-code")
    zone_before = other.display_timezone

    response = client.post(
        f"/operator/sessions/{other.id}/config",
        data={
            "name": "Renamed",
            "code": "held-code",
            "display_timezone": "Asia/Singapore",
            "tags": "pilot",
            "tags_present": "1",
        },
        follow_redirects=False,
    )

    assert response.status_code == 422, response.text
    db.expire_all()
    other = db.get(ReviewSession, other.id)
    assert (other.name, other.code) == ("Other", "other-code")
    assert other.display_timezone == zone_before
    assert session_tags.tags_for_sessions(db, [other.id])[other.id] == []


def test_session_home_save_keeps_its_own_code(
    client: TestClient, db: Session
) -> None:
    session = _create(client, db, "Mine", "my-code")

    response = client.post(
        f"/operator/sessions/{session.id}/config",
        data={"name": "Mine renamed", "code": "my-code"},
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    db.expire_all()
    assert db.get(ReviewSession, session.id).name == "Mine renamed"


def test_lobby_edit_with_a_taken_code_is_a_422_and_writes_nothing(
    client: TestClient, db: Session
) -> None:
    _create(client, db, "Holder", "lobby-held")
    other = _create(client, db, "Other", "lobby-other")

    response = client.post(
        f"/operator/sessions/{other.id}/lobby-edit",
        data={"name": "Other", "code": "lobby-held", "tags": "pilot"},
        follow_redirects=False,
    )

    assert response.status_code == 422, response.text
    db.expire_all()
    assert db.get(ReviewSession, other.id).code == "lobby-other"
    assert session_tags.tags_for_sessions(db, [other.id])[other.id] == []


def test_lobby_edit_keeps_its_own_code(client: TestClient, db: Session) -> None:
    """Every ordinary lobby Save posts the row's own code, so the check
    must exclude the session being saved."""
    session = _create(client, db, "Mine", "lobby-mine")

    response = client.post(
        f"/operator/sessions/{session.id}/lobby-edit",
        data={"name": "Mine renamed", "code": "lobby-mine", "tags": "pilot"},
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    db.expire_all()
    assert db.get(ReviewSession, session.id).name == "Mine renamed"


def test_lobby_edit_when_not_editable_ignores_a_taken_code(
    client: TestClient, db: Session
) -> None:
    """Off `is_editable` the lobby ignores Name / Code, so a taken code
    there is not refused: the tags still apply and the code is untouched."""
    _create(client, db, "Holder", "lobby-held-2")
    other = _create(client, db, "Other", "lobby-ready")
    other.status = "ready"
    db.commit()

    response = client.post(
        f"/operator/sessions/{other.id}/lobby-edit",
        data={"name": "Other", "code": "lobby-held-2", "tags": "pilot"},
        follow_redirects=False,
    )

    assert response.status_code == 303, response.text
    db.expire_all()
    assert db.get(ReviewSession, other.id).code == "lobby-ready"
    assert session_tags.tags_for_sessions(db, [other.id])[other.id] == ["pilot"]
