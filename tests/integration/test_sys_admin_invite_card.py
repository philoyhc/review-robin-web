"""Sys Admin → Accounts: the Invite card beside an Overview stub, and its
role chip (``guide/admin_pages_refine.md`` Item 3 rung 1)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings

ACCOUNTS = "/operator/sys-admin/users"


def _page(client: TestClient) -> str:
    response = client.get(ACCOUNTS)
    assert response.status_code == 200
    return response.text


def test_invite_and_overview_share_one_grid_row(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    body = _page(client)
    grid = body.split('<div class="page-grid">', 1)[1]
    assert grid.index("<h2>Invite by email</h2>") < grid.index("<h2>Overview</h2>")
    assert '<div class="card placeholder" id="accounts-overview">' in body
    overview = body.split('id="accounts-overview"', 1)[1].split("</div>", 1)[0]
    assert "will appear here" in overview
    # Overview's own close, then the grid's, before the Workspace users
    # card opens: the table card is outside the grid. (The browser test
    # measures that it spans the page.)
    after = body.split('id="accounts-overview"', 1)[1]
    between = after.split('id="accounts-table-card"', 1)[0]
    assert between.count("</div>") == 2


def test_the_role_chip_replaces_the_checkbox(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cycle chip: always solid, its label naming the state, around
    the same ``invite_as_sys_admin`` box the route reads."""
    monkeypatch.setattr(settings, "super_admin_emails", ["alice@example.edu"])
    body = _page(client)
    chip = body.split("data-invite-role-chip", 1)[1].split("</label>", 1)[0]
    head = body.split("data-invite-role-chip", 1)[0]
    assert head[head.rindex("<label") :].startswith(
        '<label class="pill pill-count tag-chip is-selected card-action-lead"'
    )
    assert 'name="invite_as_sys_admin" value="true"' in chip
    assert "checked" not in chip
    assert "data-invite-role-label>Invite as operator</span>" in chip
    assert "Also invite as sys-admin" not in body


def test_the_chip_and_buttons_share_one_row_cancel_before_invite(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The chip leads the row; Cancel then Invite follow it on the right
    (author, 2026-10-14)."""
    monkeypatch.setattr(settings, "super_admin_emails", ["alice@example.edu"])
    body = _page(client)
    form = body.split('id="invite-form"', 1)[1].split("</form>", 1)[0]
    row = form.split('<div class="card-action-row">', 1)[1]
    assert (
        row.index("data-invite-role-chip")
        < row.index("data-invite-cancel")
        < row.index("data-invite-submit")
    )


def test_without_the_chip_the_row_holds_the_buttons_alone(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A plain admin, with a super tier configured, can't invite an
    admin: no chip, and the buttons keep their order."""
    monkeypatch.setattr(settings, "sys_admin_emails", ["alice@example.edu"])
    monkeypatch.setattr(settings, "super_admin_emails", ["root@example.edu"])
    form = _page(client).split('id="invite-form"', 1)[1].split("</form>", 1)[0]
    row = form.split('<div class="card-action-row">', 1)[1]
    assert "data-invite-role-chip" not in row
    assert row.index("data-invite-cancel") < row.index("data-invite-submit")
