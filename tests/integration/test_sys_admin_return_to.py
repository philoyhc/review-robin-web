"""Sys Admin: both tabs' back link returns where the Admin visit began
(author, 2026-10-14), however the operator moves between the tabs or
acts on a page in between."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.db.models import ReviewSession

SESSIONS = "/operator/sys-admin/sessions"
ACCOUNTS = "/operator/sys-admin/users"


@pytest.fixture
def admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])


def _back(body: str) -> str:
    return body.split('<a class="back-link" href="', 1)[1].split("</a>", 1)[0]


def _session(client: TestClient, db: Session) -> ReviewSession:
    client.post("/operator/sessions", data={"name": "Spring", "code": "back-1"})
    return db.execute(
        select(ReviewSession).where(ReviewSession.code == "back-1")
    ).scalar_one()


def test_both_tabs_return_to_the_page_the_admin_link_left(
    client: TestClient, db: Session, admin: None
) -> None:
    review_session = _session(client, db)
    origin = f"/operator/sessions/{review_session.id}"
    client.get(f"/operator/sys-admin?return_to={origin}")
    expected = f'{origin}">&larr; Back to Spring'
    # Each tab, reached through the strip with no query of its own, and
    # Sessions again after Accounts.
    assert _back(client.get(ACCOUNTS).text) == expected
    assert _back(client.get(SESSIONS).text) == expected
    assert _back(client.get(f"{ACCOUNTS}?show=unused").text) == expected


def test_without_a_remembered_origin_the_back_link_is_the_lobby(
    client: TestClient, admin: None
) -> None:
    for page in (SESSIONS, ACCOUNTS):
        assert _back(client.get(page).text) == '/operator/sessions">&larr; Back to Sessions'


def test_a_forged_origin_falls_back_to_the_lobby(
    client: TestClient, admin: None
) -> None:
    client.cookies.set("rrw-admin-return-to", "https://evil.example/", path="/operator/sys-admin")
    assert _back(client.get(ACCOUNTS).text) == '/operator/sessions">&larr; Back to Sessions'


def test_a_later_admin_link_replaces_the_origin(
    client: TestClient, db: Session, admin: None
) -> None:
    review_session = _session(client, db)
    client.get(f"/operator/sys-admin?return_to=/operator/sessions/{review_session.id}")
    client.get("/operator/sys-admin?return_to=/operator/sessions")
    assert _back(client.get(ACCOUNTS).text) == '/operator/sessions">&larr; Back to Sessions'
