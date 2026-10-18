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


# --- Rung 3: URLs carry the public ID ---------------------------------------

_INTEGER_SESSION_URL = re.compile(r"/sessions/([0-9]+)(?![0-9a-z])")
_EMPTY_SESSION_LINK = re.compile(r'(?:href|action)="[^"]*/sessions/"')


def _live_session_alice_reviews(db: Session, client: TestClient) -> ReviewSession:
    """A live session alice runs and is a reviewer on, so the lobby,
    Session Home, ``/me`` and a review page all render it."""
    from ._display_field_helpers import _activate, _generate_full_matrix

    session = _create(db, client, "pid-pages")
    for kind, body in (
        ("reviewers", b"ReviewerName,ReviewerEmail\nAlice,alice@example.edu\n"),
        ("reviewees", b"RevieweeName,RevieweeEmail\nCarol,carol@example.edu\n"),
    ):
        response = client.post(
            f"/operator/sessions/{session.public_id}/{kind}/import",
            files={"file": (f"{kind}.csv", body, "text/csv")},
            follow_redirects=False,
        )
        assert response.status_code == 303, response.text
    _generate_full_matrix(client, db, session.id)
    _activate(client, db, session.id)
    db.refresh(session)
    assert session.status in ("ready", "active")
    return session


def test_an_integer_session_url_answers_404(db: Session, client: TestClient) -> None:
    session = _live_session_alice_reviews(db, client)

    assert client.get(f"/operator/sessions/{session.public_id}").status_code == 200
    assert client.get(f"/me/sessions/{session.public_id}/1").status_code == 200
    for path in (
        f"/operator/sessions/{session.id}",
        f"/operator/sessions/{session.id}/reviewers",
        f"/me/sessions/{session.id}/1",
        f"/me/sessions/{session.id}/summary",
    ):
        assert client.get(path).status_code == 404, path


def test_no_page_links_a_session_by_its_integer_id(
    db: Session, client: TestClient
) -> None:
    session = _live_session_alice_reviews(db, client)

    for path in (
        "/operator/sessions",
        f"/operator/sessions/{session.public_id}",
        "/me",
        f"/me/sessions/{session.public_id}/1",
    ):
        html = client.get(path).text
        assert f"/sessions/{session.public_id}" in html, path
        # A digit-only public ID is possible (about 1 in 10^6), so only
        # the session's own public ID is exempt.
        integers = {
            m.group(1)
            for m in _INTEGER_SESSION_URL.finditer(html)
            if m.group(1) != session.public_id
        }
        assert not integers, (path, integers)
        # A template reading a missing attribute renders it empty.
        assert "/sessions//" not in html, path
        assert not _EMPTY_SESSION_LINK.search(html), path
