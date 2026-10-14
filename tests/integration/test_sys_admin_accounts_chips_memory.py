"""Sys Admin → Accounts: the Workspace users chips stay as they were
after navigating away and back (author, 2026-10-14). A URL without
``show`` takes the chips last asked for; one with ``show`` is
remembered, every chip off included."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.web import views

ACCOUNTS = "/operator/sys-admin/users"


@pytest.fixture
def admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])


def _on(body: str) -> list[str]:
    toolbar = body.split("data-account-chips", 1)[1].split("</p>", 1)[0]
    return re.findall(r'value="([a-z_]+)"[^>]*\bchecked\b', toolbar)


def test_a_bare_visit_takes_the_chips_last_asked_for(client: TestClient, admin: None) -> None:
    assert _on(client.get(ACCOUNTS).text) == ["operators", "admins"]  # the defaults
    client.get(f"{ACCOUNTS}?show=no_role&show=unused")
    assert _on(client.get(ACCOUNTS).text) == ["no_role", "unused"]
    # Every chip off is a choice too.
    client.get(f"{ACCOUNTS}?show=")
    assert _on(client.get(ACCOUNTS).text) == []


def test_an_explicit_show_wins_over_the_remembered_one(client: TestClient, admin: None) -> None:
    client.get(f"{ACCOUNTS}?show=unused")
    assert _on(client.get(f"{ACCOUNTS}?show=admins").text) == ["admins"]
    assert _on(client.get(ACCOUNTS).text) == ["admins"]


def test_a_garbled_cookie_keeps_only_known_chips(client: TestClient, admin: None) -> None:
    client.cookies.set(views.ACCOUNT_CHIPS_COOKIE, "unused,<script>,admins", path=ACCOUNTS)
    assert _on(client.get(ACCOUNTS).text) == ["admins", "unused"]


def test_the_cookie_round_trips_every_chip_off() -> None:
    off = views.parse_account_view(show=[""], role=None, search=None, offset=0)
    value = views.account_chips_cookie(off)
    assert value == "none"
    assert views.remembered_account_chips(value) == [""]
    assert views.remembered_account_chips(None) is None
    assert views.remembered_account_chips("") is None


def test_a_chip_selected_turns_on_is_remembered(
    client: TestClient, admin: None
) -> None:
    """``?selected=`` turns the row's chip on as if clicked, and a click
    is remembered, so leaving and coming back keeps the row in view."""
    client.post(f"{ACCOUNTS}/invite", data={"email": "newbie@example.edu"})
    client.get(f"{ACCOUNTS}?show=unused")
    newbie = client.get(f"{ACCOUNTS}?show=operators&q=newbie").text
    row_id = re.search(r'data-user-id="(\d+)"', newbie)
    assert row_id is not None
    client.get(f"{ACCOUNTS}?show=unused&selected={row_id.group(1)}")
    assert _on(client.get(ACCOUNTS).text) == ["operators", "unused"]


def test_invite_lands_with_the_invitee_in_view(
    client: TestClient, admin: None
) -> None:
    """The remembered chips may hide operators; Invite selects the new
    row, which turns its chip on."""
    client.get(f"{ACCOUNTS}?show=unused")
    page = client.post(f"{ACCOUNTS}/invite", data={"email": "newbie@example.edu"})
    assert page.status_code == 200
    assert "newbie@example.edu" in page.text
    assert _on(page.text) == ["operators", "unused"]


def test_the_cookie_is_http_only_scoped_to_the_page_and_kept_a_year(
    client: TestClient, admin: None
) -> None:
    header = client.get(f"{ACCOUNTS}?show=no_role").headers["set-cookie"]
    attributes = {part.strip().lower() for part in header.split(";")}
    assert f"path={ACCOUNTS}" in attributes
    assert "httponly" in attributes
    assert "samesite=lax" in attributes
    assert f"max-age={365 * 24 * 60 * 60}" in attributes
