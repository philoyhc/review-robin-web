"""Sys Admin → Accounts: the Workspace users toolbar driven in a browser
(guide/admin_pages_refine.md Item 1). A chip submits the filter as soon
as it changes; the role and the search wait for Search; Clear keeps the
chips. The fake operator is an admin, so the page is reachable.
"""

from __future__ import annotations

import uuid
from urllib.parse import parse_qs, urlsplit

from playwright.sync_api import Page, expect

ACCOUNTS = "/operator/sys-admin/users"


def _invite(page: Page, email: str) -> None:
    page.goto(ACCOUNTS)
    page.fill("#invite-email", email)
    with page.expect_navigation():
        page.click("[data-invite-submit]")


def _query(page: Page) -> dict[str, list[str]]:
    return parse_qs(urlsplit(page.url).query, keep_blank_values=True)


def test_a_chip_filters_at_once_and_the_search_waits(page: Page) -> None:
    email = f"chip-{uuid.uuid4().hex[:8]}@example.edu"
    _invite(page, email)  # an operator, under a default chip
    page.goto(ACCOUNTS)
    table = page.locator("#users-table")
    expect(table).to_contain_text(email)

    # Turning Operators off reloads without it, at once.
    with page.expect_navigation():
        page.locator('label:has(input[name="show"][value="operators"])').click()
    assert sorted(_query(page)["show"]) == ["", "admins"]
    expect(page.locator("#users-table")).not_to_contain_text(email)
    with page.expect_navigation():
        page.locator('label:has(input[name="show"][value="operators"])').click()

    # The search waits for Search, and keeps the chips.
    page.fill('#accounts-filter input[name="q"]', email)
    expect(page.locator("#users-table tr[data-user-id]")).not_to_have_count(1)
    with page.expect_navigation():
        page.click('#accounts-filter button[type="submit"]')
    rows = page.locator("#users-table tr[data-user-id]")
    expect(rows).to_have_count(1)
    expect(rows).to_contain_text(email)
    assert _query(page)["q"] == [email]

    # Clear drops the search and keeps the chips.
    with page.expect_navigation():
        page.click("text=Clear")
    query = _query(page)
    assert "q" not in query
    assert query["show"] == ["operators", "admins"]


def test_every_chip_off_survives_the_round_trip(page: Page) -> None:
    page.goto(ACCOUNTS)
    for key in ("operators", "admins"):
        with page.expect_navigation():
            page.locator(f'label:has(input[name="show"][value="{key}"])').click()
    expect(page.get_by_text("No accounts match the chips above.")).to_be_visible()
    page.reload()
    expect(page.get_by_text("No accounts match the chips above.")).to_be_visible()
