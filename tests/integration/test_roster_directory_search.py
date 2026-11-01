"""The roster rows' directory search (segment 19Z, invite from the
directory, rung 20): the session's operators only, with the same answer
as the invite box's; and every add and edit row's two boxes carry the
picker."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ReviewSession
from app.web.routes_operator import _directory


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> None:
    from cordware.graph import FakeDirectory

    monkeypatch.setattr(_directory, "directory_or_none", lambda request: FakeDirectory())


def _session(client: TestClient, db: Session, code: str) -> ReviewSession:
    response = client.post("/operator/sessions", data={"name": "Spring", "code": code}, follow_redirects=False)
    assert response.status_code == 303, response.text
    return db.execute(select(ReviewSession).where(ReviewSession.code == code)).scalar_one()


def test_the_session_s_operator_finds_people(client: TestClient, db: Session, fake: None) -> None:
    review_session = _session(client, db, "dirs-a")
    found = client.get(f"/operator/sessions/{review_session.public_id}/directory-search", params={"q": "jan"})
    assert found.status_code == 200 and found.headers["cache-control"] == "no-store"
    assert found.json()["people"] == [
        {"name": "Jane Tan", "mail": "jane.tan@example.edu", "upn": "e0123456@example.edu",
         "address": "jane.tan@example.edu"}
    ]


def test_no_directory_reads_unavailable_with_its_reason(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    review_session = _session(client, db, "dirs-b")
    monkeypatch.setattr(_directory, "directory_or_none", lambda request: None)
    answer = client.get(f"/operator/sessions/{review_session.public_id}/directory-search", params={"q": "jan"})
    assert answer.json() == {"available": False, "people": [], "reason": "no_token"}


def test_another_session_s_operator_is_refused(make_client, alice, bob, db: Session, fake: None) -> None:
    review_session = _session(make_client(alice), db, "dirs-c")
    bob_client = make_client(bob)
    answer = bob_client.get(f"/operator/sessions/{review_session.public_id}/directory-search", params={"q": "jan"})
    assert answer.status_code in (403, 404)


@pytest.mark.parametrize(
    ("roster", "name_field", "address_field"),
    [
        ("reviewers", "name", "email"),
        ("reviewees", "name", "email_or_identifier"),
        ("observers", "display_name", "email"),
    ],
)
def test_the_add_row_s_boxes_carry_the_picker(
    client: TestClient, db: Session, roster: str, name_field: str, address_field: str
) -> None:
    review_session = _session(client, db, f"dirs-{roster}")
    if roster == "observers":
        review_session.observers_enabled = True
        db.commit()
    page = client.get(f"/operator/sessions/{review_session.public_id}/{roster}?add=1").text
    assert f'name="{name_field}" data-directory-field="name" list="directory-name-options"' in page
    assert f'name="{address_field}" data-directory-field="address" list="directory-address-options"' in page
    assert 'id="directory-name-options"' in page and "data-directory-status" in page
    assert f"/operator/sessions/{review_session.public_id}/directory-search" in page
    # Not drawn when no row is being edited.
    assert "directory-name-options" not in client.get(f"/operator/sessions/{review_session.public_id}/{roster}").text


def test_any_workspace_operator_finds_people_for_a_help_contact(client: TestClient, fake: None) -> None:
    """New session has no session yet, so its picker asks the workspace's
    search (rung 21)."""
    found = client.get("/operator/directory-search", params={"q": "arun"})
    assert found.status_code == 200 and found.headers["cache-control"] == "no-store"
    assert [p["address"] for p in found.json()["people"]] == ["arun.kumar@example.edu"]


def test_both_help_contact_boxes_carry_the_picker(client: TestClient, db: Session) -> None:
    review_session = _session(client, db, "dirs-help")
    for page in (client.get("/operator/sessions/new").text,
                 client.get(f"/operator/sessions/{review_session.public_id}").text):
        assert 'name="help_contact"' in page
        assert 'data-directory-field="contact" list="directory-contact-options"' in page
        assert 'id="directory-contact-options"' in page
        assert "/operator/directory-search" in page
