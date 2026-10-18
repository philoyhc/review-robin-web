"""19V Item 1 rung 2: every path that makes a session gives it its own
``public_id`` (``guide/segment_19V_public_id_revamp.md``)."""

from __future__ import annotations

import re

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession, User
from app.db.models.review_session import PUBLIC_ID_ALPHABET, PUBLIC_ID_LENGTH
from app.services.session_clone import clone_session
from app.services.session_config_io import serialize_session_config

_SHAPE = re.compile(f"^[{PUBLIC_ID_ALPHABET}]{{{PUBLIC_ID_LENGTH}}}$")


def _create(db: Session, client: TestClient, code: str) -> ReviewSession:
    response = client.post(
        "/operator/sessions", data={"name": "S", "code": code}, follow_redirects=False
    )
    assert response.status_code == 303, response.text
    return db.execute(select(ReviewSession).where(ReviewSession.code == code)).scalar_one()


def test_create_gives_a_session_a_public_id(db: Session, client: TestClient) -> None:
    first = _create(db, client, "pid-a")
    second = _create(db, client, "pid-b")

    assert _SHAPE.match(first.public_id)
    assert _SHAPE.match(second.public_id)
    assert first.public_id != second.public_id


def test_duplicate_draws_its_own_public_id(db: Session, client: TestClient) -> None:
    source = _create(db, client, "pid-src")
    user = db.execute(select(User)).scalars().first()

    clone = clone_session(db, source=source, user=user, mode="config")
    db.commit()

    assert _SHAPE.match(clone.public_id)
    assert clone.public_id != source.public_id


def test_a_settings_export_carries_no_public_id(db: Session, client: TestClient) -> None:
    session = _create(db, client, "pid-export")

    rows = serialize_session_config(db, session)

    assert not any("public_id" in row.field for row in rows)
    assert not any(row.value == session.public_id for row in rows)
