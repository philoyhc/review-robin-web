"""Sys Admin → Accounts: the Workspace users toolbar driven in a browser
(guide/admin_pages_refine.md Item 1). A chip submits the filter as soon
as it changes; the role and the search wait for Search; Clear keeps the
chips. The fake operator is an admin, so the page is reachable.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from urllib.parse import parse_qs, urlsplit

import httpx
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
    # Long enough for a debounced auto-submit to have fired, were there one.
    page.wait_for_timeout(500)
    assert _query(page).get("q", [""]) == [""]
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


def test_the_role_dropdown_and_the_pager(
    page: Page, api: httpx.Client, new_session: Callable[[], int]
) -> None:
    """Session role narrows on Search; the pager pages a filtered list and
    carries the filter (admin_pages_refine Item 1 rung 3)."""
    new_session()  # the fake operator owns a session
    not_an_owner = f"not-owner-{uuid.uuid4().hex[:8]}@example.edu"
    _invite(page, not_an_owner)  # an operator who owns nothing
    token = uuid.uuid4().hex[:8]
    # 201 accounts with no role, through the sign-in that creates them;
    # Unused is off by default, so no other test sees them.
    for n in range(201):
        email = f"pager-{token}-{n:03d}@example.edu"
        response = api.get(
            "/me",
            headers={
                "X-MS-CLIENT-PRINCIPAL-NAME": email,
                "X-MS-CLIENT-PRINCIPAL-ID": f"browser-{email}",
            },
        )
        assert response.status_code == 200, response.text

    page.goto(ACCOUNTS)
    page.select_option('#accounts-filter select[name="role"]', "owner")
    with page.expect_navigation():
        page.click('#accounts-filter button[type="submit"]')
    assert _query(page)["role"] == ["owner"]
    expect(page.locator("#users-table")).to_contain_text("operator@example.edu")
    expect(page.locator("#users-table")).not_to_contain_text(not_an_owner)
    expect(
        page.locator('#accounts-filter select[name="role"]')
    ).to_have_value("owner")

    page.goto(f"{ACCOUNTS}?show=unused&q=pager-{token}")
    rows = page.locator("#users-table tr[data-user-id]")
    expect(rows).to_have_count(200)
    pager = page.locator(".table-pager-cluster").first
    expect(pager.locator("summary")).to_have_text("1–200")
    with page.expect_navigation():
        pager.get_by_label("Next rows").click()
    expect(rows).to_have_count(1)
    query = _query(page)
    assert query["q"] == [f"pager-{token}"]
    assert query["show"] == ["unused"]
    assert query["offset"] == ["200"]

    # The typeahead's first list stops at the alphabetically first 200,
    # which the 201st account sorts after; typing asks again.
    page.goto(f"{ACCOUNTS}?show=unused")
    last = f"pager-{token}-200@example.edu"
    option = page.locator(f'#accounts-search-options option[value="{last}"]')
    expect(option).to_have_count(0)
    page.fill('#accounts-filter input[name="q"]', f"pager-{token}-20")
    expect(option).to_have_count(1)


def test_the_heading_and_the_filter_share_the_toolbar_top(page: Page) -> None:
    """The author, 2026-10-14: the heading leads the left half, level with
    Session role / Search on the right, and the chips sit at the left
    half's foot, level with the filter's buttons."""
    page.set_viewport_size({"width": 1280, "height": 900})
    page.goto(ACCOUNTS)
    toolbar = page.locator("#accounts-table-card .table-card-toolbar")
    heading = toolbar.locator(".toolbar-left > h2").bounding_box()
    right = toolbar.locator(".toolbar-right").bounding_box()
    chips = toolbar.locator("[data-account-chips]").bounding_box()
    assert heading and right and chips
    assert heading["x"] < right["x"]
    assert abs(heading["y"] - right["y"]) <= 2, (heading, right)
    assert abs(
        (chips["y"] + chips["height"]) - (right["y"] + right["height"])
    ) <= 2, (chips, right)
