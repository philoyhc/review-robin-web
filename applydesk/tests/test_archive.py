"""The Archive (segment AD2B rungs 5 and 6): the archived exercises the
viewer operates, newest archived first, each with Restore."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select

from applydesk import db
from applydesk.models import Exercise
from applydesk.tests._host import host_with

LOBBY = "/applydesk/operator/exercises"
ARCHIVE = f"{LOBBY}/archived"


def _client() -> TestClient:
    return TestClient(host_with(("applydesk",))[0])


def _archive(public_id: str, at: datetime) -> None:
    session = db.new_session()
    row = session.scalars(select(Exercise).where(Exercise.public_id == public_id)).one()
    row.archived_at = at
    session.commit()
    session.close()


def test_the_lobby_links_to_the_archive() -> None:
    page = _client().get(LOBBY).text
    assert f'href="{ARCHIVE}">Go to Archive</a>' in page


def test_an_empty_archive_says_so() -> None:
    reply = _client().get(ARCHIVE)
    assert reply.status_code == 200
    assert "<h1>Archived exercises</h1>" in reply.text
    assert "0 archived" in reply.text and "data-ar-empty" in reply.text


def test_archived_exercises_are_listed_newest_first() -> None:
    _archive("wa9juxbc2t", datetime(2026, 11, 20, 1, 0, tzinfo=UTC))  # RA-2027
    _archive("n5wg8tjr3e", datetime(2026, 11, 21, 1, 0, tzinfo=UTC))  # Graduate Travel Grant
    page = _client().get(ARCHIVE).text
    assert "2 archived" in page
    assert page.index("Graduate Travel Grant") < page.index("Recruitment and Selection")
    assert "2026-11-20 09:00" in page  # RA-2027's, in Singapore time
    assert page.count("data-ar-restore>Restore") == 2
